import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import MagicMock, patch

import app as nexus_app


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps({
            "candidates": [{
                "content": {"parts": [{"text": "Te recomiendo revisar el catálogo."}]}
            }]
        }).encode("utf-8")


class FakeJsonResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class NexusApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.requests_file_patch = patch.object(
            nexus_app, "REQUESTS_FILE", Path(self.temp_dir.name) / "requests.json"
        )
        self.database_file_patch = patch.object(
            nexus_app, "DATABASE_FILE", Path(self.temp_dir.name) / "nexus.sqlite3"
        )
        self.database_url_patch = patch.object(nexus_app, "DATABASE_URL", "")
        self.admin_password_patch = patch.dict(os.environ, {
            "NEXUS_ADMIN_PASSWORD": "test-admin-password",
            "NEXUS_SECRET_KEY": "test-session-signing-key",
        })
        self.requests_file_patch.start()
        self.database_file_patch.start()
        self.database_url_patch.start()
        self.admin_password_patch.start()
        self.client = nexus_app.app.test_client()
        login = self.client.post("/api/admin/login", json={"password": "test-admin-password"})
        self.csrf_token = login.get_json()["csrf_token"]

    def tearDown(self):
        self.admin_password_patch.stop()
        self.database_url_patch.stop()
        self.database_file_patch.stop()
        self.requests_file_patch.stop()
        self.temp_dir.cleanup()

    def test_catalog_is_available_and_has_expected_categories(self):
        response = self.client.get("/api/products")

        self.assertEqual(response.status_code, 200)
        products = response.get_json()
        self.assertEqual(len(products), 34)
        self.assertEqual(len({item["category"] for item in products}), 8)
        self.assertEqual(sum(item["category"] == "Componentes" for item in products), 17)
        self.assertEqual(len({item["id"] for item in products}), len(products))
        self.assertTrue(all(item.get("image") and item.get("description") for item in products))

    def test_missing_catalog_returns_an_explicit_server_error(self):
        with patch.object(nexus_app, "PRODUCTS_FILE", Path(self.temp_dir.name) / "missing.json"):
            response = self.client.get("/api/products")

        self.assertEqual(response.status_code, 500)
        self.assertIn("no está disponible", response.get_json()["error"])

    def test_health_check(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")
        self.assertEqual(response.get_json()["database"], "SQLite")

    def test_mysql_schema_initializes_only_nexus_tables(self):
        connection = MagicMock()

        nexus_app.initialize_mysql(connection)

        statements = [
            call.args[0] for call in connection.execute.call_args_list
        ]
        joined_schema = "\n".join(statements).lower()
        self.assertIn("create table if not exists purchase_requests", joined_schema)
        self.assertIn("create table if not exists store_checkout_payments", joined_schema)
        self.assertNotIn("create table if not exists libros", joined_schema)
        self.assertNotIn("drop table", joined_schema)

    def test_health_check_reports_mysql_when_configured(self):
        connection = MagicMock()
        connection_manager = MagicMock()
        connection_manager.__enter__.return_value = connection
        with (
            patch.object(nexus_app, "DATABASE_URL", "mysql://user:pass@localhost/nexus"),
            patch.object(nexus_app, "DATABASE_BACKEND", "mysql"),
            patch.object(nexus_app, "server_connection", return_value=connection_manager),
            patch.object(nexus_app, "initialize_server"),
        ):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["database"], "MySQL")
        connection.execute.assert_called_once_with("SELECT 1")

    def test_malformed_origin_does_not_break_health_check(self):
        response = self.client.get("/health", headers={"Origin": "http://localhost:invalid"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_frontend_and_its_assets_are_served(self):
        page = self.client.get("/")
        styles = self.client.get("/static/styles.css")
        script = self.client.get("/static/app.js")
        favicon = self.client.get("/static/favicon.svg")
        self.addCleanup(page.close)
        self.addCleanup(styles.close)
        self.addCleanup(script.close)
        self.addCleanup(favicon.close)

        self.assertEqual(page.status_code, 200)
        self.assertIn(b"NEXUS Copilot", page.data)
        self.assertIn(b"productDetailsOverlay", page.data)
        self.assertIn(b"Ficha y gu\xc3\xada", page.data)
        self.assertIn(b"data-add-product", page.data)
        self.assertEqual(styles.status_code, 200)
        self.assertEqual(script.status_code, 200)
        self.assertEqual(favicon.status_code, 200)

    def test_request_total_is_calculated_from_catalog(self):
        response = self.client.post("/api/requests", json={
            "client": "Ana Pérez",
            "email": "ana@example.com",
            "note": "Equipo para estudiar",
            "items": [{"product_id": "lap-lenovo-slim3", "quantity": 2}],
        })

        self.assertEqual(response.status_code, 201)
        created = response.get_json()
        self.assertEqual(created["total"], 2199900 * 2)
        self.assertEqual(created["status"], "pending")
        self.assertEqual(len(self.client.get("/api/requests").get_json()), 1)
        self.assertTrue(nexus_app.DATABASE_FILE.exists())

    def test_requests_are_saved_in_sqlite_and_survive_a_new_client(self):
        response = self.client.post("/api/requests", json={
            "client": "Ana Pérez",
            "email": "ana@example.com",
            "items": [{"product_id": "lap-lenovo-slim3", "quantity": 1}],
        })
        created = response.get_json()

        second_client = nexus_app.app.test_client()
        self.assertEqual(second_client.get("/api/requests").status_code, 401)
        second_client.post("/api/admin/login", json={"password": "test-admin-password"})
        persisted = second_client.get("/api/requests").get_json()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(persisted), 1)
        self.assertEqual(persisted[0]["id"], created["id"])
        self.assertEqual(persisted[0]["items"][0]["product_id"], "lap-lenovo-slim3")

    def test_existing_json_requests_are_imported_once(self):
        legacy_request = {
            "id": "legacy-request",
            "client": "Cliente anterior",
            "email": "anterior@example.com",
            "note": "",
            "items": [{
                "product_id": "lap-lenovo-slim3",
                "name": "Lenovo IdeaPad Slim 3",
                "quantity": 1,
                "unit_price": 2199900,
            }],
            "total": 2199900,
            "status": "pending",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        nexus_app.REQUESTS_FILE.write_text(
            json.dumps([legacy_request]),
            encoding="utf-8",
        )

        first_read = self.client.get("/api/requests").get_json()
        nexus_app.REQUESTS_FILE.write_text("[]", encoding="utf-8")
        second_read = self.client.get("/api/requests").get_json()

        self.assertEqual(first_read[0]["id"], "legacy-request")
        self.assertEqual(second_read[0]["id"], "legacy-request")

    def test_sqlite_enforces_request_item_constraints(self):
        self.client.get("/api/requests")

        with closing(sqlite3.connect(nexus_app.DATABASE_FILE)) as connection:
            with connection:
                connection.execute("PRAGMA foreign_keys = ON")
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO purchase_request_items
                            (request_id, product_id, name, quantity, unit_price)
                        VALUES ('missing', 'product', 'Product', 1, 100)
                        """
                    )

    def test_duplicate_product_lines_are_aggregated(self):
        response = self.client.post("/api/requests", json={
            "client": "Ana Pérez",
            "email": "ana@example.com",
            "items": [
                {"product_id": "lap-lenovo-slim3", "quantity": 2},
                {"product_id": "lap-lenovo-slim3", "quantity": 3},
            ],
        })

        self.assertEqual(response.status_code, 201)
        created = response.get_json()
        self.assertEqual(len(created["items"]), 1)
        self.assertEqual(created["items"][0]["quantity"], 5)
        self.assertEqual(created["total"], 2199900 * 5)

    def test_duplicate_product_lines_cannot_bypass_quantity_limit(self):
        response = self.client.post("/api/requests", json={
            "client": "Ana Pérez",
            "email": "ana@example.com",
            "items": [
                {"product_id": "lap-lenovo-slim3", "quantity": 20},
                {"product_id": "lap-lenovo-slim3", "quantity": 1},
            ],
        })

        self.assertEqual(response.status_code, 400)

    def test_invalid_email_and_quantity_are_rejected(self):
        invalid_email = self.client.post("/api/requests", json={
            "client": "Ana",
            "email": "ana@",
            "items": [{"product_id": "lap-lenovo-slim3", "quantity": 1}],
        })
        invalid_quantity = self.client.post("/api/requests", json={
            "client": "Ana",
            "email": "ana@example.com",
            "items": [{"product_id": "lap-lenovo-slim3", "quantity": 21}],
        })

        self.assertEqual(invalid_email.status_code, 400)
        self.assertEqual(invalid_quantity.status_code, 400)

    def test_request_rejects_non_text_fields_and_malformed_product_ids(self):
        invalid_client = self.client.post("/api/requests", json={
            "client": ["Ana"],
            "email": "ana@example.com",
            "items": [{"product_id": "lap-lenovo-slim3", "quantity": 1}],
        })
        invalid_product_id = self.client.post("/api/requests", json={
            "client": "Ana",
            "email": "ana@example.com",
            "items": [{"product_id": {"id": "lap-lenovo-slim3"}, "quantity": 1}],
        })

        self.assertEqual(invalid_client.status_code, 400)
        self.assertEqual(invalid_product_id.status_code, 400)

    def test_pending_request_can_only_be_decided_once(self):
        created = self.client.post("/api/requests", json={
            "client": "Ana",
            "email": "ana@example.com",
            "items": [{"product_id": "lap-lenovo-slim3", "quantity": 1}],
        }).get_json()

        decision = self.client.patch(
            f"/api/requests/{created['id']}",
            json={"status": "approved"},
            headers={"X-CSRF-Token": self.csrf_token},
        )
        second_decision = self.client.patch(
            f"/api/requests/{created['id']}",
            json={"status": "rejected"},
            headers={"X-CSRF-Token": self.csrf_token},
        )

        self.assertEqual(decision.status_code, 200)
        self.assertEqual(decision.get_json()["status"], "approved")
        self.assertEqual(second_decision.status_code, 409)

    def test_admin_routes_require_authentication_and_csrf(self):
        anonymous = nexus_app.app.test_client()
        self.assertEqual(anonymous.get("/api/requests").status_code, 401)
        self.assertEqual(
            anonymous.patch("/api/requests/example", json={"status": "approved"}).status_code,
            401,
        )
        missing_csrf = self.client.patch(
            "/api/requests/example", json={"status": "approved"}
        )
        self.assertEqual(missing_csrf.status_code, 403)

    def test_admin_login_rejects_bad_password_and_does_not_expose_secret(self):
        anonymous = nexus_app.app.test_client()
        response = anonymous.post("/api/admin/login", json={"password": "wrong-password"})

        self.assertEqual(response.status_code, 401)
        self.assertNotIn("test-admin-password", response.get_data(as_text=True))

    def test_checkout_requires_sandbox_configuration(self):
        with patch.dict(os.environ, {
            "MERCADOPAGO_ACCESS_TOKEN": "",
            "MERCADOPAGO_WEBHOOK_SECRET": "",
            "NEXUS_PUBLIC_URL": "",
            "NEXUS_PAYMENT_MODE": "test",
        }):
            response = self.client.post("/api/checkout", json={})

        self.assertEqual(response.status_code, 503)
        self.assertIn("checkout de prueba", response.get_json()["error"])

    def test_store_status_is_closed_by_default_and_does_not_expose_secrets(self):
        secret = "TEST-private-token"
        with patch.dict(os.environ, {
            "MERCADOPAGO_ACCESS_TOKEN": secret,
            "MERCADOPAGO_PUBLIC_KEY": "TEST-public-key",
            "MERCADOPAGO_WEBHOOK_SECRET": "private-webhook-secret",
            "NEXUS_PUBLIC_URL": "https://store.example",
            "NEXUS_PAYMENT_MODE": "test",
        }, clear=True):
            response = self.client.get("/api/store/status")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["configured"])
        self.assertFalse(response.get_json()["live_sales_enabled"])
        self.assertTrue(response.get_json()["missing"])
        self.assertNotIn(secret, response.get_data(as_text=True))
        self.assertNotIn("private-webhook-secret", response.get_data(as_text=True))

    def test_store_checkout_without_sandbox_configuration_uses_demo_mode(self):
        with patch.dict(os.environ, {
            "MERCADOPAGO_ACCESS_TOKEN": "TEST-private-token",
            "MERCADOPAGO_PUBLIC_KEY": "TEST-public-key",
            "MERCADOPAGO_WEBHOOK_SECRET": "webhook-signing-secret",
            "NEXUS_PUBLIC_URL": "https://store.example",
            "NEXUS_PAYMENT_MODE": "test",
            "NEXUS_STORE_TEST_ENABLED": "false",
        }, clear=True):
            response = self.client.post("/api/store/orders", json={
                "client": "Ana",
                "email": "ana@example.com",
                "phone": "+57 300 123 4567",
                "address": "Calle 10 # 20-30",
                "city": "Medellín",
                "items": [{"product_id": "lap-lenovo-slim3", "quantity": 1}],
            })

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["mode"], "demo")

    def test_store_checkout_simulates_an_order_without_mercadopago_credentials(self):
        payload = {
            "client": "Ana",
            "email": "ana@example.com",
            "phone": "+57 300 123 4567",
            "address": "Calle 10 # 20-30",
            "city": "Medellín",
            "items": [{"product_id": "lap-lenovo-slim3", "quantity": 1}],
        }
        with patch.dict(os.environ, {}, clear=True):
            status = self.client.get("/api/store/status")
            created = self.client.post("/api/store/orders", json=payload)

        self.assertEqual(status.status_code, 200)
        self.assertTrue(status.get_json()["demo_mode"])
        self.assertFalse(status.get_json()["configured"])
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.get_json()["mode"], "demo")
        order = created.get_json()["order"]
        self.assertEqual(order["total"], 2199900)
        self.assertEqual(order["items"][0]["name"], "Lenovo IdeaPad Slim 3")

        requests = self.client.get("/api/requests").get_json()
        saved_order = next(item for item in requests if item["id"] == order["id"])
        self.assertEqual(saved_order["client"], payload["client"])
        self.assertEqual(saved_order["payment_status"], "simulated")
        self.assertEqual(saved_order["address"], payload["address"])

    def test_embedded_store_payment_uses_server_total_and_persists_delivery(self):
        environment = {
            "MERCADOPAGO_ACCESS_TOKEN": "TEST-private-token",
            "MERCADOPAGO_PUBLIC_KEY": "TEST-public-key",
            "MERCADOPAGO_WEBHOOK_SECRET": "webhook-signing-secret",
            "NEXUS_PUBLIC_URL": "https://store.example",
            "NEXUS_PAYMENT_MODE": "test",
            "NEXUS_STORE_TEST_ENABLED": "true",
        }
        payload = {
            "client": "Ana",
            "email": "ana@example.com",
            "phone": "+57 300 123 4567",
            "address": "Calle 10 # 20-30",
            "city": "Medellín",
            "items": [{"product_id": "lap-lenovo-slim3", "quantity": 1}],
        }
        provider_payment = {
            "id": 123456789,
            "status": "approved",
            "external_reference": None,
            "transaction_amount": 2199900,
            "currency_id": "COP",
            "live_mode": False,
        }
        with patch.dict(os.environ, environment, clear=True):
            created = self.client.post("/api/store/orders", json=payload)
            self.assertEqual(created.status_code, 201)
            order = created.get_json()["order"]
            provider_payment["external_reference"] = order["id"]
            with patch.object(
                nexus_app, "urlopen", return_value=FakeJsonResponse(provider_payment)
            ) as mocked_urlopen:
                payment_response = self.client.post("/api/store/payments", json={
                    "order_id": order["id"],
                    "payment": {
                        "token": "opaque-card-token",
                        "payment_method_id": "visa",
                        "installments": 1,
                        "issuer_id": "123",
                        "payer": {"email": "attacker@example.com"},
                    },
                })

        self.assertEqual(payment_response.status_code, 200)
        self.assertEqual(payment_response.get_json()["status"], "approved")
        provider_request = mocked_urlopen.call_args.args[0]
        payment_data = json.loads(provider_request.data)
        self.assertEqual(payment_data["transaction_amount"], 2199900.0)
        self.assertEqual(payment_data["payer"]["email"], "ana@example.com")
        self.assertEqual(provider_request.get_header("X-idempotency-key"), order["id"])
        self.assertIn("TEST-private-token", provider_request.get_header("Authorization"))

        requests = self.client.get("/api/requests").get_json()
        saved_order = next(item for item in requests if item["id"] == order["id"])
        self.assertEqual(saved_order["payment_status"], "approved")
        self.assertEqual(saved_order["address"], payload["address"])
        self.assertEqual(saved_order["city"], payload["city"])

    def test_embedded_store_payment_rejects_a_live_provider_response(self):
        environment = {
            "MERCADOPAGO_ACCESS_TOKEN": "TEST-private-token",
            "MERCADOPAGO_PUBLIC_KEY": "TEST-public-key",
            "MERCADOPAGO_WEBHOOK_SECRET": "webhook-signing-secret",
            "NEXUS_PUBLIC_URL": "https://store.example",
            "NEXUS_PAYMENT_MODE": "test",
            "NEXUS_STORE_TEST_ENABLED": "true",
        }
        with patch.dict(os.environ, environment, clear=True):
            created = self.client.post("/api/store/orders", json={
                "client": "Ana",
                "email": "ana@example.com",
                "phone": "+57 300 123 4567",
                "address": "Calle 10 # 20-30",
                "city": "Medellín",
                "items": [{"product_id": "lap-lenovo-slim3", "quantity": 1}],
            }).get_json()
            payment_response = {
                "id": 123456789,
                "status": "approved",
                "external_reference": created["order"]["id"],
                "transaction_amount": 2199900,
                "currency_id": "COP",
                "live_mode": True,
            }
            with patch.object(
                nexus_app, "urlopen", return_value=FakeJsonResponse(payment_response)
            ):
                response = self.client.post("/api/store/payments", json={
                    "order_id": created["order"]["id"],
                    "payment": {
                        "token": "opaque-card-token",
                        "payment_method_id": "visa",
                        "installments": 1,
                        "payer": {},
                    },
                })

        self.assertEqual(response.status_code, 502)
        self.assertIn("verificar", response.get_json()["error"])

    def test_embedded_store_webhook_updates_payment_without_preference_id(self):
        environment = {
            "MERCADOPAGO_ACCESS_TOKEN": "TEST-private-token",
            "MERCADOPAGO_PUBLIC_KEY": "TEST-public-key",
            "MERCADOPAGO_WEBHOOK_SECRET": "webhook-signing-secret",
            "NEXUS_PUBLIC_URL": "https://store.example",
            "NEXUS_PAYMENT_MODE": "test",
            "NEXUS_STORE_TEST_ENABLED": "true",
        }
        with patch.dict(os.environ, environment, clear=True):
            order = self.client.post("/api/store/orders", json={
                "client": "Ana",
                "email": "ana@example.com",
                "phone": "+57 300 123 4567",
                "address": "Calle 10 # 20-30",
                "city": "Medellín",
                "items": [{"product_id": "lap-lenovo-slim3", "quantity": 1}],
            }).get_json()["order"]
            provider_payment = {
                "id": 123456789,
                "status": "pending",
                "external_reference": order["id"],
                "transaction_amount": 2199900,
                "currency_id": "COP",
                "live_mode": False,
            }
            with patch.object(
                nexus_app, "urlopen", return_value=FakeJsonResponse(provider_payment)
            ):
                payment = self.client.post("/api/store/payments", json={
                    "order_id": order["id"],
                    "payment": {
                        "token": "opaque-card-token",
                        "payment_method_id": "visa",
                        "installments": 1,
                        "payer": {},
                    },
                })
            self.assertEqual(payment.status_code, 200)

            request_id = "provider-request-id"
            timestamp = "1792150000"
            manifest = f"id:123456789;request-id:{request_id};ts:{timestamp};"
            signature = nexus_app.hmac.new(
                environment["MERCADOPAGO_WEBHOOK_SECRET"].encode(),
                manifest.encode(),
                digestmod="sha256",
            ).hexdigest()
            provider_payment["status"] = "approved"
            with patch.object(
                nexus_app, "fetch_mercadopago_payment", return_value=provider_payment
            ):
                webhook = self.client.post(
                    "/api/payments/webhook?data.id=123456789",
                    json={"type": "payment", "data": {"id": "123456789"}},
                    headers={
                        "x-request-id": request_id,
                        "x-signature": f"ts={timestamp},v1={signature}",
                    },
                )

        self.assertEqual(webhook.status_code, 200)
        self.assertEqual(
            self.client.get(f"/api/checkout/{order['id']}").get_json()["status"],
            "approved",
        )

    def test_sqlite_adds_shipping_columns_to_an_existing_database(self):
        with nexus_app.sqlite_connection() as connection:
            connection.execute("""
                CREATE TABLE purchase_requests (
                    id TEXT PRIMARY KEY,
                    client TEXT NOT NULL,
                    email TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    total INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    decided_at TEXT
                )
            """)
            nexus_app.initialize_sqlite(connection)
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(purchase_requests)")
            }

        self.assertTrue({"phone", "address", "city"}.issubset(columns))

    def test_checkout_never_accepts_production_credentials(self):
        with patch.dict(os.environ, {
            "MERCADOPAGO_ACCESS_TOKEN": "APP-production-token",
            "MERCADOPAGO_WEBHOOK_SECRET": "webhook-signing-secret",
            "NEXUS_PUBLIC_URL": "https://store.example",
            "NEXUS_PAYMENT_MODE": "live",
        }):
            response = self.client.post("/api/checkout", json={})

        self.assertEqual(response.status_code, 503)

    def test_checkout_uses_server_prices_and_sandbox_url(self):
        environment = {
            "MERCADOPAGO_ACCESS_TOKEN": "TEST-private-token",
            "MERCADOPAGO_WEBHOOK_SECRET": "webhook-signing-secret",
            "NEXUS_PUBLIC_URL": "https://store.example",
            "NEXUS_PAYMENT_MODE": "test",
        }
        provider_response = {
            "id": "preference-test-123",
            "sandbox_init_point": "https://sandbox.mercadopago.com.co/checkout/v1/redirect?pref_id=123",
            "init_point": "https://www.mercadopago.com.co/checkout/v1/redirect?pref_id=123",
        }
        with (
            patch.dict(os.environ, environment),
            patch.object(
                nexus_app, "urlopen", return_value=FakeJsonResponse(provider_response)
            ) as mocked_urlopen,
        ):
            response = self.client.post("/api/checkout", json={
                "client": "Ana",
                "email": "ana@example.com",
                "items": [{"product_id": "lap-lenovo-slim3", "quantity": 1}],
            })

        self.assertEqual(response.status_code, 201)
        result = response.get_json()
        self.assertEqual(result["mode"], "test")
        self.assertIn("sandbox.mercadopago.com.co", result["checkout_url"])
        provider_request = mocked_urlopen.call_args.args[0]
        self.assertEqual(provider_request.get_header("Authorization"), "Bearer TEST-private-token")
        self.assertEqual(provider_request.get_header("X-idempotency-key"), result["request"]["id"])
        preference = json.loads(provider_request.data)
        self.assertEqual(preference["items"][0]["unit_price"], 2199900)
        self.assertEqual(preference["items"][0]["currency_id"], "COP")
        self.assertEqual(preference["external_reference"], result["request"]["id"])
        self.assertEqual(
            self.client.get(f"/api/checkout/{result['request']['id']}").get_json()["status"],
            "pending",
        )

    def test_checkout_webhook_verifies_signature_and_provider_payment(self):
        environment = {
            "MERCADOPAGO_ACCESS_TOKEN": "TEST-private-token",
            "MERCADOPAGO_WEBHOOK_SECRET": "webhook-signing-secret",
            "NEXUS_PUBLIC_URL": "https://store.example",
            "NEXUS_PAYMENT_MODE": "test",
        }
        preference_response = {
            "id": "preference-test-123",
            "sandbox_init_point": "https://sandbox.mercadopago.com.co/checkout/v1/redirect?pref_id=123",
        }
        with (
            patch.dict(os.environ, environment),
            patch.object(nexus_app, "urlopen", return_value=FakeJsonResponse(preference_response)),
        ):
            checkout = self.client.post("/api/checkout", json={
                "client": "Ana",
                "email": "ana@example.com",
                "items": [{"product_id": "lap-lenovo-slim3", "quantity": 1}],
            }).get_json()

        order_id = checkout["request"]["id"]
        payment_id = "123456789"
        request_id = "provider-request-id"
        timestamp = "1792150000"
        manifest = f"id:{payment_id};request-id:{request_id};ts:{timestamp};"
        signature = nexus_app.hmac.new(
            environment["MERCADOPAGO_WEBHOOK_SECRET"].encode(),
            manifest.encode(),
            digestmod="sha256",
        ).hexdigest()
        provider_payment = {
            "id": int(payment_id),
            "external_reference": order_id,
            "preference_id": "preference-test-123",
            "currency_id": "COP",
            "transaction_amount": 2199900,
            "status": "approved",
            "live_mode": False,
        }
        with (
            patch.dict(os.environ, environment),
            patch.object(nexus_app, "fetch_mercadopago_payment", return_value=provider_payment),
        ):
            webhook = self.client.post(
                f"/api/payments/webhook?data.id={payment_id}",
                json={"type": "payment", "data": {"id": payment_id}},
                headers={
                    "x-request-id": request_id,
                    "x-signature": f"ts={timestamp},v1={signature}",
                },
            )

        self.assertEqual(webhook.status_code, 200)
        status = self.client.get(f"/api/checkout/{order_id}")
        self.assertEqual(status.get_json()["status"], "approved")

    def test_checkout_webhook_rejects_invalid_signature(self):
        with patch.dict(os.environ, {
            "MERCADOPAGO_ACCESS_TOKEN": "TEST-private-token",
            "MERCADOPAGO_WEBHOOK_SECRET": "webhook-signing-secret",
            "NEXUS_PUBLIC_URL": "https://store.example",
            "NEXUS_PAYMENT_MODE": "test",
        }):
            response = self.client.post(
                "/api/payments/webhook?data.id=123",
                json={"type": "payment", "data": {"id": "123"}},
                headers={"x-request-id": "request-id", "x-signature": "ts=1,v1=invalid"},
            )

        self.assertEqual(response.status_code, 401)

    def test_ai_status_never_exposes_the_api_key(self):
        secret = "private-test-key"
        with patch.dict(os.environ, {"GEMINI_API_KEY": secret}):
            response = self.client.get("/api/ai/status")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["configured"])
        self.assertNotIn(secret, response.get_data(as_text=True))

    def test_ai_chat_explains_missing_server_key(self):
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.post("/api/ai/chat", json={
                "messages": [{"role": "user", "content": "Busco un portátil"}]
            })

        self.assertEqual(response.status_code, 503)
        self.assertIn("no está configurado", response.get_json()["error"])

    def test_ai_chat_rejects_a_malformed_conversation(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "private-test-key"}):
            response = self.client.post("/api/ai/chat", json={
                "messages": [
                    {"role": "assistant", "content": "Hola"},
                    {"role": "user", "content": "Recomiéndame un equipo"},
                ]
            })

        self.assertEqual(response.status_code, 400)

    def test_ai_chat_calls_gemini_from_the_server(self):
        secret = "private-test-key"
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": secret, "GEMINI_MODEL": "gemini-test"}),
            patch.object(nexus_app, "urlopen", return_value=FakeResponse()) as mocked_urlopen,
        ):
            response = self.client.post("/api/ai/chat", json={
                "messages": [{"role": "user", "content": "Busco un portátil"}]
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["answer"], "Te recomiendo revisar el catálogo.")
        upstream_request = mocked_urlopen.call_args.args[0]
        self.assertEqual(upstream_request.get_header("X-goog-api-key"), secret)
        self.assertNotIn(secret, upstream_request.full_url)
        upstream_payload = json.loads(upstream_request.data)
        system_instruction = upstream_payload["system_instruction"]["parts"][0]["text"]
        self.assertIn("preguntas generales", system_instruction)
        self.assertIn("No inventes hechos", system_instruction)
        self.assertIn("haz una pregunta breve de aclaración", system_instruction)
        self.assertEqual(upstream_payload["generationConfig"]["temperature"], 0.2)
        self.assertEqual(upstream_payload["generationConfig"]["maxOutputTokens"], 1000)
        catalogue_prompt = upstream_payload["contents"][0]["parts"][0]["text"]
        self.assertIn("pagos Sandbox", catalogue_prompt)
        self.assertIn("no cobra dinero real", catalogue_prompt)
        self.assertNotIn("sin pagos ni envíos reales", catalogue_prompt)

    def test_ai_chat_explains_gemini_model_not_found(self):
        secret = "private-test-key"
        error = HTTPError(
            "https://generativelanguage.googleapis.com/",
            404,
            "Not Found",
            {},
            None,
        )
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": secret, "GEMINI_MODEL": "missing-model"}),
            patch.object(nexus_app, "urlopen", side_effect=error),
        ):
            response = self.client.post("/api/ai/chat", json={
                "messages": [{"role": "user", "content": "Hola"}]
            })

        self.assertEqual(response.status_code, 502)
        self.assertIn("HTTP 404", response.get_json()["error"])
        self.assertIn("modelo solicitado", response.get_json()["error"])
        self.assertNotIn(secret, response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
