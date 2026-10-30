from __future__ import annotations

import json
import hmac
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from threading import Lock
from time import monotonic, time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from flask import Flask, jsonify, request, send_from_directory, session


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
PRODUCTS_FILE = STATIC_DIR / "products.json"
REQUESTS_FILE = BASE_DIR / "data" / "requests.json"
SCHEMA_FILE = BASE_DIR / "data" / "schema.sql"
MYSQL_SCHEMA_FILE = BASE_DIR / "data" / "schema.mysql.sql"
SQLITE_SCHEMA_FILE = BASE_DIR / "data" / "schema.sqlite.sql"
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DATABASE_BACKEND = (
    "mysql" if DATABASE_URL.lower().startswith(("mysql://", "mysql+pymysql://"))
    else "postgresql" if DATABASE_URL
    else "sqlite"
)
DATABASE_FILE = Path(os.environ.get(
    "NEXUS_DATABASE_PATH",
    str(BASE_DIR / "data" / "nexus.sqlite3"),
)).expanduser()
if not DATABASE_FILE.is_absolute():
    DATABASE_FILE = BASE_DIR / DATABASE_FILE
REQUESTS_LOCK = Lock()
ADMIN_LOGIN_LOCK = Lock()
ADMIN_LOGIN_ATTEMPTS = {}
VALID_STATUSES = {"pending", "approved", "rejected"}


class MySQLDatabaseError(RuntimeError):
    pass


app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
app.secret_key = os.environ.get("NEXUS_SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=(
        os.environ.get("NEXUS_COOKIE_SECURE", "").lower() == "true"
        or os.environ.get("NEXUS_PUBLIC_URL", "").lower().startswith("https://")
    ),
)
if not os.environ.get("NEXUS_SECRET_KEY"):
    app.logger.warning(
        "NEXUS_SECRET_KEY no está configurada; las sesiones se invalidarán al reiniciar."
    )


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if (
            not session.get("nexus_admin")
            or session.get("admin_expires_at", 0) < int(time())
        ):
            session.clear()
            return jsonify(error="Inicia sesión como administrador para continuar."), 401
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            token = session.get("csrf_token", "")
            if not token or not hmac.compare_digest(
                token, request.headers.get("X-CSRF-Token", "")
            ):
                return jsonify(error="La sesión expiró o la solicitud no es válida. Vuelve a iniciar sesión."), 403
        return view(*args, **kwargs)

    return wrapped


@app.after_request
def allow_local_frontend(response):
    origin = request.headers.get("Origin", "")
    if origin:
        try:
            parsed_origin = urlparse(origin)
            is_local_origin = (
                parsed_origin.scheme in {"http", "https"}
                and parsed_origin.hostname in {"127.0.0.1", "localhost"}
                and parsed_origin.port is not None
            )
        except ValueError:
            is_local_origin = False
        if is_local_origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Allow-Headers"] += ", X-CSRF-Token"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, OPTIONS"
            response.headers["Access-Control-Allow-Credentials"] = "true"

    if request.method == "OPTIONS":
        response.status_code = 200

    return response


def read_json(path: Path, fallback):
    try:
        with path.open(encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return fallback


def read_catalog():
    catalog = read_json(PRODUCTS_FILE, None)
    if not isinstance (catalog, list):
        raise ValueError("El catálogo debe contener una lista JSON.")

    product_ids = set()
    for product in catalog:
        if not isinstance(product, dict):
            raise ValueError("El catálogo contiene un producto inválido.")
        product_id = product.get("id")
        text_fields = ("id", "name", "category", "subtitle", "description", "image")
        if (
            any(not isinstance(product.get(field), str) or not product[field] for field in text_fields)
            or product_id in product_ids
            or isinstance(product.get("price"), bool)
            or not isinstance(product.get("price"), int)
            or product["price"] < 0
            or isinstance(product.get("rating"), bool)
            or not isinstance(product.get("rating"), (int, float))
            or not 0 <= product["rating"] <= 5
            or isinstance(product.get("stock"), bool)
            or not isinstance(product.get("stock"), int)
            or product["stock"] < 0
        ):
            raise ValueError("El catálogo contiene un producto inválido.")
        product_ids.add(product_id)

    return catalog


def postgres_connection():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as error:
        raise RuntimeError(
            "PostgreSQL está configurado, pero falta instalar psycopg. "
            "Ejecuta: python -m pip install -r requirements.txt"
        ) from error

    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


class MySQLConnection:
    def __init__(self, connection, cursor_class):
        self.connection = connection
        self.cursor_class = cursor_class

    def execute(self, query, parameters=()):
        cursor = self.connection.cursor(self.cursor_class)
        cursor.execute(query, parameters)
        return cursor

    def executemany(self, query, parameters):
        cursor = self.connection.cursor(self.cursor_class)
        cursor.executemany(query, parameters)
        return cursor


@contextmanager
def mysql_connection():
    try:
        import pymysql
        from pymysql.cursors import DictCursor
    except ImportError as error:
        raise MySQLDatabaseError(
            "MySQL está configurado, pero falta instalar PyMySQL. "
            "Ejecuta: python -m pip install -r requirements.txt"
        ) from error

    parsed = urlparse(DATABASE_URL)
    if not parsed.hostname or not parsed.path.strip("/"):
        raise MySQLDatabaseError(
            "DATABASE_URL de MySQL debe incluir el host y el nombre de la base de datos."
        )
    try:
        connection = pymysql.connect(
            host=parsed.hostname,
            port=parsed.port or 3306,
            user=unquote(parsed.username or ""),
            password=unquote(parsed.password or ""),
            database=unquote(parsed.path.lstrip("/")),
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
            connect_timeout=10,
        )
    except pymysql.MySQLError as error:
        app.logger.error("No se pudo conectar con MySQL: %s", error)
        raise MySQLDatabaseError(
            "No se pudo conectar con la base MySQL. Revisa DATABASE_URL y el servidor."
        ) from error
    try:
        yield MySQLConnection(connection, DictCursor)
        connection.commit()
    except pymysql.MySQLError as error:
        connection.rollback()
        app.logger.error("Error ejecutando una operación en MySQL: %s", error)
        raise MySQLDatabaseError(
            "MySQL rechazó una operación. Revisa la conexión y el esquema de NEXUS."
        ) from error
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def server_connection():
    return mysql_connection() if DATABASE_BACKEND == "mysql" else postgres_connection()


def initialize_postgres(connection):
    with SCHEMA_FILE.open(encoding="utf-8") as schema:
        connection.execute(schema.read())


def initialize_mysql(connection):
    with MYSQL_SCHEMA_FILE.open(encoding="utf-8") as schema:
        for statement in schema.read().split(";"):
            if statement.strip():
                connection.execute(statement)


def initialize_server(connection):
    if DATABASE_BACKEND == "mysql":
        initialize_mysql(connection)
    else:
        initialize_postgres(connection)


@contextmanager
def sqlite_connection():
    DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_FILE, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def insert_sqlite_request(connection, item):
    required_fields = ("id", "client", "email", "note", "total", "status", "created_at", "items")
    if (
        not isinstance(item, dict)
        or any(field not in item for field in required_fields)
        or not isinstance(item["items"], list)
        or not item["items"]
    ):
        raise ValueError("Una solicitud existente no tiene un formato válido.")

    connection.execute(
        """
        INSERT INTO purchase_requests
            (id, client, email, phone, address, city, note, total, status, created_at, decided_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item["id"],
            item["client"],
            item["email"],
            item.get("phone", ""),
            item.get("address", ""),
            item.get("city", ""),
            item["note"],
            item["total"],
            item["status"],
            item["created_at"],
            item.get("decided_at"),
        ),
    )
    connection.executemany(
        """
        INSERT INTO purchase_request_items
            (request_id, product_id, name, quantity, unit_price)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                item["id"],
                product["product_id"],
                product["name"],
                product["quantity"],
                product["unit_price"],
            )
            for product in item["items"]
        ],
    )


def initialize_sqlite(connection):
    with SQLITE_SCHEMA_FILE.open(encoding="utf-8") as schema:
        connection.executescript(schema.read())

    request_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(purchase_requests)")
    }
    for column, definition in (
        ("phone", "TEXT NOT NULL DEFAULT ''"),
        ("address", "TEXT NOT NULL DEFAULT ''"),
        ("city", "TEXT NOT NULL DEFAULT ''"),
    ):
        if column not in request_columns:
            connection.execute(
                f"ALTER TABLE purchase_requests ADD COLUMN {column} {definition}"
            )

    migration = "legacy_json_requests_imported"
    already_imported = connection.execute(
        "SELECT 1 FROM app_migrations WHERE name = ?",
        (migration,),
    ).fetchone()
    if already_imported:
        return

    connection.execute("BEGIN IMMEDIATE")
    try:
        already_imported = connection.execute(
            "SELECT 1 FROM app_migrations WHERE name = ?",
            (migration,),
        ).fetchone()
        if already_imported:
            connection.commit()
            return

        legacy_requests = read_json(REQUESTS_FILE, [])
        if not isinstance(legacy_requests, list):
            raise ValueError("El archivo de solicitudes existente debe contener una lista JSON.")
        for item in legacy_requests:
            insert_sqlite_request(connection, item)
        connection.execute(
            "INSERT INTO app_migrations (name) VALUES (?)",
            (migration,),
        )
        connection.commit()
    except (sqlite3.Error, ValueError, TypeError, KeyError):
        connection.rollback()
        raise


def database_datetime(value):
    if not isinstance(value, datetime):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def get_requests():
    if DATABASE_BACKEND == "mysql":
        with server_connection() as connection:
            initialize_server(connection)
            requests_by_id = {}
            for row in connection.execute(
                """
                SELECT
                    r.id, r.client, r.email, r.phone, r.address, r.city, r.note, r.total,
                    r.status, r.created_at, r.decided_at,
                    COALESCE(
                        (SELECT cp.status FROM checkout_payments AS cp WHERE cp.request_id = r.id),
                        (SELECT sp.status FROM store_checkout_payments AS sp WHERE sp.request_id = r.id)
                    ) AS payment_status
                FROM purchase_requests AS r
                ORDER BY r.created_at DESC, r.id
                """
            ):
                item = dict(row)
                item["created_at"] = database_datetime(item["created_at"])
                if item["decided_at"] is not None:
                    item["decided_at"] = database_datetime(item["decided_at"])
                item["items"] = []
                requests_by_id[item["id"]] = item
            for row in connection.execute(
                """
                SELECT request_id, product_id, name, quantity, unit_price
                FROM purchase_request_items
                ORDER BY id
                """
            ):
                requests_by_id[row["request_id"]]["items"].append({
                    "product_id": row["product_id"],
                    "name": row["name"],
                    "quantity": row["quantity"],
                    "unit_price": row["unit_price"],
                })
        return list(requests_by_id.values())

    if DATABASE_URL:
        with server_connection() as connection:
            initialize_server(connection)
            rows = connection.execute(
                """
                SELECT
                    r.id,
                    r.client,
                    r.email,
                    r.phone,
                    r.address,
                    r.city,
                    r.note,
                    r.total,
                    r.status,
                    r.created_at,
                    r.decided_at,
                    COALESCE(
                        (SELECT cp.status FROM checkout_payments AS cp WHERE cp.request_id = r.id),
                        (SELECT sp.status FROM store_checkout_payments AS sp WHERE sp.request_id = r.id)
                    ) AS payment_status,
                    COALESCE(
                        jsonb_agg(jsonb_build_object(
                            'product_id', i.product_id,
                            'name', i.name,
                            'quantity', i.quantity,
                            'unit_price', i.unit_price
                        ) ORDER BY i.id) FILTER (WHERE i.id IS NOT NULL),
                        '[]'::jsonb
                    ) AS items
                FROM purchase_requests AS r
                LEFT JOIN purchase_request_items AS i ON i.request_id = r.id
                GROUP BY r.id
                ORDER BY r.created_at DESC
                """
            ).fetchall()
        return [
            {
                **row,
                "created_at": row["created_at"].isoformat(),
                **(
                    {"decided_at": row["decided_at"].isoformat()}
                    if row["decided_at"] is not None
                    else {}
                ),
            }
            for row in rows
        ]

    with sqlite_connection() as connection:
        initialize_sqlite(connection)
        requests_by_id = {}
        for row in connection.execute(
            """
            SELECT
                r.id, r.client, r.email, r.phone, r.address, r.city, r.note, r.total,
                r.status, r.created_at, r.decided_at,
                COALESCE(
                    (SELECT cp.status FROM checkout_payments AS cp WHERE cp.request_id = r.id),
                    (SELECT sp.status FROM store_checkout_payments AS sp WHERE sp.request_id = r.id)
                ) AS payment_status
            FROM purchase_requests AS r
            ORDER BY created_at DESC, id
            """
        ):
            item = dict(row)
            item["items"] = []
            requests_by_id[item["id"]] = item
        for row in connection.execute(
            """
            SELECT request_id, product_id, name, quantity, unit_price
            FROM purchase_request_items
            ORDER BY id
            """
        ):
            requests_by_id[row["request_id"]]["items"].append({
                "product_id": row["product_id"],
                "name": row["name"],
                "quantity": row["quantity"],
                "unit_price": row["unit_price"],
            })
        return list(requests_by_id.values())


def save_request(created):
    if DATABASE_URL:
        with server_connection() as connection:
            initialize_server(connection)
            connection.execute(
                """
                INSERT INTO purchase_requests
                    (id, client, email, phone, address, city, note, total, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    created["id"],
                    created["client"],
                    created["email"],
                    created.get("phone", ""),
                    created.get("address", ""),
                    created.get("city", ""),
                    created["note"],
                    created["total"],
                    created["status"],
                    datetime.fromisoformat(created["created_at"]),
                ),
            )
            connection.executemany(
                """
                INSERT INTO purchase_request_items
                    (request_id, product_id, name, quantity, unit_price)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    (
                        created["id"],
                        item["product_id"],
                        item["name"],
                        item["quantity"],
                        item["unit_price"],
                    )
                    for item in created["items"]
                ],
            )
        return

    with sqlite_connection() as connection:
        initialize_sqlite(connection)
        insert_sqlite_request(connection, created)


def decide_request(request_id, status):
    if not DATABASE_URL:
        with sqlite_connection() as connection:
            initialize_sqlite(connection)
            decided_at = datetime.now(timezone.utc).isoformat()
            updated = connection.execute(
                """
                UPDATE purchase_requests
                SET status = ?, decided_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (status, decided_at, request_id),
            )
            if updated.rowcount == 0:
                exists = connection.execute(
                    "SELECT 1 FROM purchase_requests WHERE id = ?",
                    (request_id,),
                ).fetchone()
                return None, "already_decided" if exists else "not_found"

            target = dict(connection.execute(
                """
                SELECT id, client, email, phone, address, city, note, total, status, created_at, decided_at
                FROM purchase_requests
                WHERE id = ?
                """,
                (request_id,),
            ).fetchone())
            target["items"] = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT product_id, name, quantity, unit_price
                    FROM purchase_request_items
                    WHERE request_id = ?
                    ORDER BY id
                    """,
                    (request_id,),
                )
            ]
            return target, None

    with server_connection() as connection:
        initialize_server(connection)
        target = connection.execute(
            """
            SELECT id, client, email, phone, address, city, note, total, status, created_at, decided_at
            FROM purchase_requests
            WHERE id = %s
            FOR UPDATE
            """,
            (request_id,),
        ).fetchone()
        if target is None:
            return None, "not_found"
        if target["status"] != "pending":
            return None, "already_decided"

        decided_at = datetime.now(timezone.utc)
        connection.execute(
            """
            UPDATE purchase_requests
            SET status = %s, decided_at = %s
            WHERE id = %s
            """,
            (status, decided_at, request_id),
        )
        target["status"] = status
        target["decided_at"] = decided_at
        request_items = connection.execute(
            """
            SELECT product_id, name, quantity, unit_price
            FROM purchase_request_items
            WHERE request_id = %s
            ORDER BY id
            """,
            (request_id,),
        ).fetchall()

    return {
        **target,
        "created_at": database_datetime(target["created_at"]),
        "decided_at": database_datetime(target["decided_at"]),
        "items": request_items,
    }, None


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/api/products")
def products():
    try:
        return jsonify(read_catalog())
    except (OSError, ValueError) as error:
        app.logger.error("No se pudo cargar el catálogo: %s", error)
        return jsonify(error="El catálogo no está disponible en este momento."), 500


@app.get("/api/ai/status")
def ai_status():
    return jsonify(
        configured=bool(os.environ.get("GEMINI_API_KEY", "").strip()),
        provider="Gemini",
        model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip(),
    )


@app.post("/api/ai/chat")
def ai_chat():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return jsonify(
            error=(
                "El asistente de IA todavía no está configurado. "
                "Consulta el README para activar Gemini en el servidor."
            )
        ), 503

    body = request.get_json(silent=True)
    messages = body.get("messages") if isinstance(body, dict) else None
    if not isinstance(messages, list) or not 1 <= len(messages) <= 8:
        return jsonify(error="Envía entre 1 y 8 mensajes para iniciar la consulta."), 400

    contents = []
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in {"user", "assistant"}:
            return jsonify(error="El historial contiene un mensaje inválido."), 400
        text = message.get("content")
        max_length = 1200 if message["role"] == "user" else 8000
        if not isinstance(text, str) or not text.strip() or len(text) > max_length:
            return jsonify(error="El texto de un mensaje está vacío o supera el límite permitido."), 400
        contents.append({
            "role": "user" if message["role"] == "user" else "model",
            "parts": [{"text": text.strip()}],
        })

    if messages[0]["role"] != "user" or messages[-1]["role"] != "user":
        return jsonify(error="La conversación debe comenzar y terminar con un mensaje del usuario."), 400
    if any(messages[index]["role"] == messages[index - 1]["role"] for index in range(1, len(messages))):
        return jsonify(error="Los mensajes del historial deben alternar entre usuario y asistente."), 400

    try:
        catalog = read_catalog()
    except (OSError, ValueError) as error:
        app.logger.error("No se pudo cargar el catálogo para el asistente: %s", error)
        return jsonify(error="El catálogo no está disponible en este momento."), 500

    catalog_context = [
        {
            "name": item.get("name"),
            "category": item.get("category"),
            "price": item.get("price"),
            "description": item.get("description", ""),
        }
        for item in catalog
        if isinstance(item, dict)
    ]
    contents[0]["parts"][0]["text"] = (
        "Responde en español de forma clara y útil también a preguntas generales. "
        "Cuando te pregunten por productos, precios, disponibilidad o compras de "
        "NEXUS, usa exclusivamente el catálogo proporcionado: compara precios en "
        "COP, no inventes stock ni especificaciones, aclara que precios y "
        "disponibilidad son referenciales y recuerda que el checkout integrado "
        "solo permite pagos Sandbox: no cobra dinero real, no reserva inventario "
        "ni genera envíos reales. Las solicitudes registradas son para revisión "
        "y no equivalen a una compra confirmada. Si no sabes algo, reconócelo; "
        "no afirmes que realizas compras ni solicites datos personales.\n\n"
        f"Catálogo disponible:\n{json.dumps(catalog_context, ensure_ascii=False)}"
    ) + "\n\nPregunta del cliente:\n" + contents[0]["parts"][0]["text"]

    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
    if not model or len(model) > 100:
        return jsonify(error="La configuración del modelo de IA no es válida."), 500
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{quote(model, safe='')}:generateContent"
    )
    payload = json.dumps(
        {
            "system_instruction": {
                "parts": [{
                    "text": (
                        "Eres NEXUS Copilot, un asistente útil, respetuoso y riguroso. "
                        "Responde preguntas generales y la pregunta concreta del "
                        "usuario, incluso si no trata de NEXUS o tecnología, siempre "
                        "que puedas hacerlo de forma responsable. Contesta en el idioma "
                        "del usuario; si escribe en "
                        "español, usa español claro y natural. Empieza por la respuesta "
                        "directa y añade solo el contexto, los pasos o un ejemplo que "
                        "ayuden a resolver su duda. Si falta un dato imprescindible, "
                        "haz una pregunta breve de aclaración en vez de adivinar. "
                        "No inventes hechos, cifras, fuentes, citas, capacidades ni "
                        "resultados; si no estás seguro, dilo claramente, explica qué "
                        "parte es incierta y ofrece una forma útil de comprobarla. "
                        "No presentes información que pueda haber cambiado como actual "
                        "si no puedes verificarla. Distingue los hechos de tus "
                        "estimaciones y recomendaciones. Para preguntas sobre productos, "
                        "precios, stock o compras de NEXUS, usa únicamente el contexto "
                        "del catálogo y respeta sus avisos de precios referenciales y "
                        "checkout Sandbox. No afirmes que se completó una compra real. "
                        "En temas médicos, legales o financieros, ofrece información "
                        "general prudente y recomienda acudir a un profesional cuando "
                        "la decisión dependa de circunstancias personales."
                    )
                }]
            },
            "contents": contents,
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1000},
        }
    ).encode("utf-8")
    upstream_request = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )

    try:
        with urlopen(upstream_request, timeout=25) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        app.logger.error("Gemini respondió con HTTP %s.", error.code)
        provider_errors = {
            400: (
                "Gemini rechazó la solicitud (HTTP 400). Revisa que el modelo "
                "configurado sea compatible con generateContent."
            ),
            403: (
                "Google rechazó la clave o sus permisos (HTTP 403). Verifica "
                "que la clave de AI Studio esté activa y habilitada para Gemini."
            ),
            404: (
                "Gemini no encontró el modelo solicitado (HTTP 404). Confirma "
                "que GEMINI_MODEL sea un modelo disponible para generateContent."
            ),
            429: (
                "Se alcanzó el límite de uso de Gemini (HTTP 429). Revisa la "
                "cuota y el estado de facturación del proyecto en Google AI Studio."
            ),
        }
        return jsonify(
            error=provider_errors.get(
                error.code,
                f"Gemini rechazó la consulta (HTTP {error.code}). Revisa la configuración e inténtalo de nuevo.",
            )
        ), 502
    except (URLError, TimeoutError) as error:
        app.logger.error("No se pudo conectar con Gemini: %s", error)
        return jsonify(error="No fue posible conectar con el asistente. Inténtalo de nuevo."), 502
    except (UnicodeDecodeError, json.JSONDecodeError):
        app.logger.error("Gemini devolvió una respuesta que no es JSON válido.")
        return jsonify(error="El asistente devolvió una respuesta no válida. Inténtalo de nuevo."), 502

    if not isinstance(result, dict):
        app.logger.error("Gemini devolvió un objeto JSON con formato inválido.")
        return jsonify(error="El asistente devolvió una respuesta no válida. Inténtalo de nuevo."), 502
    candidates = result.get("candidates", [])
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        return jsonify(error="El asistente no generó una respuesta. Inténtalo de nuevo."), 502
    response_content = candidates[0].get("content", {})
    parts = response_content.get("parts", []) if isinstance(response_content, dict) else []
    answer = "\n".join(
        part["text"].strip()
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str) and part["text"].strip()
    )
    if not answer:
        return jsonify(error="El asistente devolvió una respuesta vacía. Inténtalo de nuevo."), 502
    return jsonify(answer=answer)


@app.get("/api/requests")
@admin_required
def list_requests():
    with REQUESTS_LOCK:
        items = get_requests()
    return jsonify(sorted(items, key=lambda item: item["created_at"], reverse=True))


def build_request(body):
    if not isinstance(body, dict):
        return None, ("El cuerpo debe ser un objeto JSON.", 400)

    client_value = body.get("client", "")
    email_value = body.get("email", "")
    phone_value = body.get("phone", "")
    address_value = body.get("address", "")
    city_value = body.get("city", "")
    note_value = body.get("note", "")
    if not all(
        isinstance(value, str)
        for value in (client_value, email_value, phone_value, address_value, city_value, note_value)
    ):
        return None, ("Los datos del comprador deben enviarse como texto.", 400)
    client = client_value.strip()
    email = email_value.strip()
    phone = phone_value.strip()
    address = address_value.strip()
    city = city_value.strip()
    note = note_value.strip()[:500]
    submitted_items = body.get("items")
    if not client or len(client) > 100:
        return None, ("Escribe un nombre de cliente válido (máximo 100 caracteres).", 400)
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 150:
        return None, ("Escribe un correo electrónico válido.", 400)
    if len(phone) > 30 or len(address) > 250 or len(city) > 100:
        return None, ("Los datos de entrega superan el límite permitido.", 400)
    if not isinstance(submitted_items, list) or not submitted_items:
        return None, ("Agrega al menos un producto a la solicitud.", 400)

    try:
        catalog = read_catalog()
    except (OSError, ValueError) as error:
        app.logger.error("No se pudo cargar el catálogo para la solicitud: %s", error)
        return None, ("El catálogo no está disponible en este momento.", 500)

    products_by_id = {item["id"]: item for item in catalog}
    if len(submitted_items) > len(products_by_id):
        return None, ("La solicitud contiene demasiadas líneas de productos.", 400)

    quantities = {}
    for submitted in submitted_items:
        if not isinstance(submitted, dict):
            return None, ("Hay un producto inválido en la solicitud.", 400)
        product_id = submitted.get("product_id")
        if not isinstance(product_id, str):
            return None, ("El identificador de producto debe ser texto.", 400)
        product = products_by_id.get(product_id)
        quantity = submitted.get("quantity")
        if product is None or not isinstance(quantity, int) or isinstance(quantity, bool) or not 1 <= quantity <= 20:
            return None, ("Producto o cantidad inválidos. Cada cantidad debe estar entre 1 y 20.", 400)
        combined_quantity = quantities.get(product_id, 0) + quantity
        if combined_quantity > 20:
            return None, ("La cantidad total de cada producto no puede superar 20.", 400)
        quantities[product_id] = combined_quantity

    items = [
        {
            "product_id": product_id,
            "name": products_by_id[product_id]["name"],
            "quantity": quantity,
            "unit_price": products_by_id[product_id]["price"],
        }
        for product_id, quantity in quantities.items()
    ]
    total = sum(item["unit_price"] * item["quantity"] for item in items)

    return {
        "id": str(uuid4()),
        "client": client,
        "email": email,
        "phone": phone,
        "address": address,
        "city": city,
        "note": note,
        "items": items,
        "total": total,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, None


def payment_test_configuration():
    access_token = os.environ.get("MERCADOPAGO_ACCESS_TOKEN", "").strip()
    public_url = os.environ.get("NEXUS_PUBLIC_URL", "").strip().rstrip("/")
    webhook_secret = os.environ.get("MERCADOPAGO_WEBHOOK_SECRET", "").strip()
    try:
        parsed_url = urlparse(public_url)
        valid_public_url = (
            parsed_url.scheme == "https"
            and bool(parsed_url.hostname)
            and not parsed_url.username
            and not parsed_url.password
            and not parsed_url.query
            and not parsed_url.fragment
        )
    except ValueError:
        valid_public_url = False

    return {
        "ready": (
            os.environ.get("NEXUS_PAYMENT_MODE", "test").strip().lower() == "test"
            and access_token.startswith("TEST-")
            and valid_public_url
            and bool(webhook_secret)
        ),
        "access_token": access_token,
        "public_url": public_url,
        "webhook_secret": webhook_secret,
    }


def brick_payment_configuration():
    configuration = payment_test_configuration()
    public_key = os.environ.get("MERCADOPAGO_PUBLIC_KEY", "").strip()
    missing = []
    if os.environ.get("NEXUS_STORE_TEST_ENABLED", "").strip().lower() != "true":
        missing.append("Activar explícitamente el checkout Sandbox con NEXUS_STORE_TEST_ENABLED=true.")
    if not configuration["ready"]:
        missing.append(
            "Configurar token TEST-, secreto del webhook y URL pública HTTPS de Mercado Pago."
        )
    if not public_key.startswith("TEST-"):
        missing.append("Configurar la clave pública TEST- de Mercado Pago.")
    return {
        **configuration,
        "public_key": public_key if public_key.startswith("TEST-") else "",
        "ready": not missing,
        "missing": missing,
    }


def create_mercadopago_preference(order, configuration):
    public_url = configuration["public_url"]
    preference = {
        "items": [
            {
                "id": item["product_id"],
                "title": item["name"][:250],
                "quantity": item["quantity"],
                "currency_id": "COP",
                "unit_price": float(item["unit_price"]),
            }
            for item in order["items"]
        ],
        "payer": {"name": order["client"], "email": order["email"]},
        "external_reference": order["id"],
        "notification_url": f"{public_url}/api/payments/webhook",
        "back_urls": {
            "success": f"{public_url}/?checkout=success",
            "failure": f"{public_url}/?checkout=failure",
            "pending": f"{public_url}/?checkout=pending",
        },
        "auto_return": "approved",
        "metadata": {"order_id": order["id"], "environment": "test"},
    }
    upstream_request = Request(
        "https://api.mercadopago.com/checkout/preferences",
        data=json.dumps(preference).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {configuration['access_token']}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": order["id"],
        },
        method="POST",
    )
    try:
        with urlopen(upstream_request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        app.logger.error("Mercado Pago rechazó una preferencia de prueba (HTTP %s).", error.code)
        raise RuntimeError("Mercado Pago no pudo iniciar el pago de prueba.") from error
    except (URLError, TimeoutError) as error:
        app.logger.error("No se pudo conectar con Mercado Pago: %s", error)
        raise RuntimeError("No fue posible conectar con Mercado Pago.") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        app.logger.error("Mercado Pago devolvió una respuesta de preferencia no válida.")
        raise RuntimeError("Mercado Pago devolvió una respuesta no válida.") from error

    if not isinstance(result, dict):
        raise RuntimeError("Mercado Pago devolvió una respuesta no válida.")
    preference_id = result.get("id")
    checkout_url = result.get("sandbox_init_point")
    if (
        not isinstance(preference_id, str)
        or not preference_id
        or not isinstance(checkout_url, str)
    ):
        raise RuntimeError("Mercado Pago no generó un enlace de pago de prueba.")
    parsed_checkout = urlparse(checkout_url)
    hostname = parsed_checkout.hostname or ""
    if parsed_checkout.scheme != "https" or not any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in ("mercadopago.com", "mercadopago.com.co")
    ):
        app.logger.error("Mercado Pago devolvió un dominio de checkout no permitido.")
        raise RuntimeError("Mercado Pago devolvió un enlace de pago no válido.")

    return preference_id, checkout_url


def save_checkout_payment(order, preference_id, checkout_url):
    now = datetime.now(timezone.utc).isoformat()
    if DATABASE_URL:
        with server_connection() as connection:
            initialize_server(connection)
            connection.execute(
                """
                INSERT INTO purchase_requests
                    (id, client, email, note, total, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    order["id"],
                    order["client"],
                    order["email"],
                    order["note"],
                    order["total"],
                    order["status"],
                    datetime.fromisoformat(order["created_at"]),
                ),
            )
            connection.executemany(
                """
                INSERT INTO purchase_request_items
                    (request_id, product_id, name, quantity, unit_price)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    (
                        order["id"],
                        item["product_id"],
                        item["name"],
                        item["quantity"],
                        item["unit_price"],
                    )
                    for item in order["items"]
                ],
            )
            connection.execute(
                """
                INSERT INTO checkout_payments
                    (request_id, preference_id, checkout_url, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    order["id"],
                    preference_id,
                    checkout_url,
                    "pending",
                    datetime.fromisoformat(now),
                    datetime.fromisoformat(now),
                ),
            )
        return

    with sqlite_connection() as connection:
        initialize_sqlite(connection)
        insert_sqlite_request(connection, order)
        connection.execute(
            """
            INSERT INTO checkout_payments
                (request_id, preference_id, checkout_url, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (order["id"], preference_id, checkout_url, "pending", now, now),
        )


def save_store_order(order, payment_status="pending"):
    now = datetime.now(timezone.utc)
    if DATABASE_URL:
        with server_connection() as connection:
            initialize_server(connection)
            connection.execute(
                """
                INSERT INTO purchase_requests
                    (id, client, email, phone, address, city, note, total, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    order["id"],
                    order["client"],
                    order["email"],
                    order["phone"],
                    order["address"],
                    order["city"],
                    order["note"],
                    order["total"],
                    order["status"],
                    datetime.fromisoformat(order["created_at"]),
                ),
            )
            connection.executemany(
                """
                INSERT INTO purchase_request_items
                    (request_id, product_id, name, quantity, unit_price)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    (
                        order["id"],
                        item["product_id"],
                        item["name"],
                        item["quantity"],
                        item["unit_price"],
                    )
                    for item in order["items"]
                ],
            )
            connection.execute(
                """
                INSERT INTO store_checkout_payments
                    (request_id, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s)
                """,
                (order["id"], payment_status, now, now),
            )
        return

    with sqlite_connection() as connection:
        initialize_sqlite(connection)
        insert_sqlite_request(connection, order)
        connection.execute(
            """
            INSERT INTO store_checkout_payments
                (request_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (order["id"], payment_status, now.isoformat(), now.isoformat()),
        )


def store_order_status(order_id):
    if DATABASE_URL:
        with server_connection() as connection:
            initialize_server(connection)
            return connection.execute(
                """
                SELECT r.id, r.email, r.total, p.status, p.provider_payment_id, p.updated_at
                FROM purchase_requests AS r
                JOIN store_checkout_payments AS p ON p.request_id = r.id
                WHERE r.id = %s
                """,
                (order_id,),
            ).fetchone()

    with sqlite_connection() as connection:
        initialize_sqlite(connection)
        row = connection.execute(
            """
            SELECT r.id, r.email, r.total, p.status, p.provider_payment_id, p.updated_at
            FROM purchase_requests AS r
            JOIN store_checkout_payments AS p ON p.request_id = r.id
            WHERE r.id = ?
            """,
            (order_id,),
        ).fetchone()
        return dict(row) if row else None


def update_store_payment(order_id, payment_id, status):
    now = datetime.now(timezone.utc)
    if DATABASE_URL:
        with server_connection() as connection:
            initialize_server(connection)
            payment = connection.execute(
                """
                SELECT status FROM store_checkout_payments
                WHERE request_id = %s FOR UPDATE
                """,
                (order_id,),
            ).fetchone()
            if payment is None:
                return False
            if payment["status"] in {"approved", "refunded"} and status != "refunded":
                return True
            connection.execute(
                """
                UPDATE store_checkout_payments
                SET status = %s, provider_payment_id = %s, updated_at = %s
                WHERE request_id = %s
                """,
                (status, payment_id, now, order_id),
            )
        return True

    with sqlite_connection() as connection:
        initialize_sqlite(connection)
        payment = connection.execute(
            "SELECT status FROM store_checkout_payments WHERE request_id = ?",
            (order_id,),
        ).fetchone()
        if payment is None:
            return False
        if payment["status"] in {"approved", "refunded"} and status != "refunded":
            return True
        connection.execute(
            """
            UPDATE store_checkout_payments
            SET status = ?, provider_payment_id = ?, updated_at = ?
            WHERE request_id = ?
            """,
            (status, payment_id, now.isoformat(), order_id),
        )
    return True


def create_mercadopago_brick_payment(order, payment_data, configuration):
    submitted_payer = payment_data["payer"]
    payer = {"email": order["email"]}
    identification = submitted_payer.get("identification")
    if isinstance(identification, dict):
        identification_type = identification.get("type")
        identification_number = identification.get("number")
        if (
            isinstance(identification_type, str)
            and isinstance(identification_number, str)
            and identification_type
            and identification_number
        ):
            payer["identification"] = {
                "type": identification_type[:20],
                "number": identification_number[:30],
            }

    payload = {
        "transaction_amount": float(order["total"]),
        "token": payment_data["token"],
        "description": f"Compra NEXUS {order['id']}",
        "installments": payment_data["installments"],
        "payment_method_id": payment_data["payment_method_id"],
        "payer": payer,
        "external_reference": order["id"],
        "notification_url": f"{configuration['public_url']}/api/payments/webhook",
        "metadata": {"order_id": order["id"], "environment": "test"},
    }
    issuer_id = payment_data.get("issuer_id")
    if isinstance(issuer_id, (str, int)) and str(issuer_id).isdigit():
        payload["issuer_id"] = str(issuer_id)

    upstream_request = Request(
        "https://api.mercadopago.com/v1/payments",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {configuration['access_token']}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": order["id"],
        },
        method="POST",
    )
    try:
        with urlopen(upstream_request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        app.logger.error("Mercado Pago rechazó un pago de prueba (HTTP %s).", error.code)
        raise RuntimeError("Mercado Pago no pudo procesar el pago de prueba.") from error
    except (URLError, TimeoutError) as error:
        app.logger.error("No se pudo conectar con Mercado Pago: %s", error)
        raise RuntimeError("No fue posible conectar con Mercado Pago.") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        app.logger.error("Mercado Pago devolvió una respuesta de pago no válida.")
        raise RuntimeError("Mercado Pago devolvió una respuesta no válida.") from error

    if not isinstance(result, dict):
        raise RuntimeError("Mercado Pago devolvió una respuesta no válida.")
    return result


def checkout_payment_status(request_id):
    if DATABASE_URL:
        with server_connection() as connection:
            initialize_server(connection)
            return connection.execute(
                """
                SELECT c.status, c.provider_payment_id, c.preference_id, c.updated_at, r.total
                FROM checkout_payments AS c
                JOIN purchase_requests AS r ON r.id = c.request_id
                WHERE c.request_id = %s
                """,
                (request_id,),
            ).fetchone()

    with sqlite_connection() as connection:
        initialize_sqlite(connection)
        row = connection.execute(
            """
            SELECT c.status, c.provider_payment_id, c.preference_id, c.updated_at, r.total
            FROM checkout_payments AS c
            JOIN purchase_requests AS r ON r.id = c.request_id
            WHERE c.request_id = ?
            """,
            (request_id,),
        ).fetchone()
        return dict(row) if row else None


def update_checkout_payment(request_id, payment_id, status):
    now = datetime.now(timezone.utc)
    if DATABASE_URL:
        with server_connection() as connection:
            initialize_server(connection)
            payment = connection.execute(
                """
                SELECT status FROM checkout_payments
                WHERE request_id = %s FOR UPDATE
                """,
                (request_id,),
            ).fetchone()
            if payment is None:
                return False
            if payment["status"] in {"approved", "refunded"} and status != "refunded":
                return True
            connection.execute(
                """
                UPDATE checkout_payments
                SET status = %s, provider_payment_id = %s, updated_at = %s
                WHERE request_id = %s
                """,
                (status, payment_id, now, request_id),
            )
        return True

    with sqlite_connection() as connection:
        initialize_sqlite(connection)
        payment = connection.execute(
            "SELECT status FROM checkout_payments WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if payment is None:
            return False
        if payment["status"] in {"approved", "refunded"} and status != "refunded":
            return True
        connection.execute(
            """
            UPDATE checkout_payments
            SET status = ?, provider_payment_id = ?, updated_at = ?
            WHERE request_id = ?
            """,
            (status, payment_id, now.isoformat(), request_id),
        )
    return True


def verify_mercadopago_signature(data_id):
    signature = request.headers.get("x-signature", "")
    request_id = request.headers.get("x-request-id", "")
    parts = dict(
        part.split("=", 1)
        for part in signature.split(",")
        if "=" in part
    )
    timestamp = parts.get("ts", "")
    provided_signature = parts.get("v1", "")
    if not timestamp or not provided_signature or not request_id:
        return False
    manifest = f"id:{data_id.lower()};request-id:{request_id};ts:{timestamp};"
    expected = hmac.new(
        payment_test_configuration()["webhook_secret"].encode("utf-8"),
        manifest.encode("utf-8"),
        digestmod="sha256",
    ).hexdigest()
    return hmac.compare_digest(expected, provided_signature)


def fetch_mercadopago_payment(payment_id, access_token):
    upstream_request = Request(
        f"https://api.mercadopago.com/v1/payments/{quote(payment_id, safe='')}",
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    try:
        with urlopen(upstream_request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        app.logger.error("Mercado Pago no confirmó el pago (HTTP %s).", error.code)
        raise RuntimeError("No se pudo verificar el pago con Mercado Pago.") from error
    except (URLError, TimeoutError) as error:
        app.logger.error("No se pudo consultar el pago en Mercado Pago: %s", error)
        raise RuntimeError("No se pudo verificar el pago con Mercado Pago.") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        app.logger.error("Mercado Pago devolvió una consulta de pago no válida.")
        raise RuntimeError("Mercado Pago devolvió una respuesta no válida.") from error
    if not isinstance(result, dict):
        raise RuntimeError("Mercado Pago devolvió una respuesta no válida.")
    return result


@app.get("/api/payments/status")
def payments_status():
    configuration = payment_test_configuration()
    return jsonify(configured=configuration["ready"], mode="test", provider="Mercado Pago")


@app.get("/api/store/status")
def store_status():
    configuration = brick_payment_configuration()
    return jsonify(
        configured=configuration["ready"],
        demo_mode=not configuration["ready"],
        mode="test",
        provider="Mercado Pago",
        checkout="Card Payment Brick",
        public_key=configuration["public_key"],
        live_sales_enabled=False,
        missing=configuration["missing"],
    )


@app.post("/api/store/orders")
def create_store_order():
    configuration = brick_payment_configuration()
    order, error = build_request(request.get_json(silent=True))
    if error:
        message, status = error
        return jsonify(error=message), status
    if not re.fullmatch(r"[0-9+() -]{7,30}", order["phone"]):
        return jsonify(error="Escribe un teléfono válido para la entrega."), 400
    if len(order["address"]) < 5:
        return jsonify(error="Escribe una dirección de entrega válida."), 400
    if len(order["city"]) < 2:
        return jsonify(error="Escribe una ciudad válida."), 400

    try:
        with REQUESTS_LOCK:
            save_store_order(
                order,
                payment_status="pending" if configuration["ready"] else "simulated",
            )
    except (OSError, sqlite3.Error, ValueError):
        app.logger.exception("No se pudo guardar el pedido de prueba.")
        return jsonify(error="No se pudo iniciar el pedido. Inténtalo de nuevo."), 503

    return jsonify(
        order={
            "id": order["id"],
            "total": order["total"],
            "items": order["items"],
        },
        mode="test" if configuration["ready"] else "demo",
    ), 201


@app.post("/api/store/payments")
def process_store_payment():
    configuration = brick_payment_configuration()
    if not configuration["ready"]:
        return jsonify(error="El checkout integrado no está disponible para pruebas."), 503

    body = request.get_json(silent=True)
    order_id = body.get("order_id") if isinstance(body, dict) else None
    payment_data = body.get("payment") if isinstance(body, dict) else None
    if not isinstance(order_id, str) or not re.fullmatch(r"[\da-f-]{36}", order_id, re.IGNORECASE):
        return jsonify(error="El identificador del pedido no es válido."), 400
    if not isinstance(payment_data, dict):
        return jsonify(error="Los datos tokenizados del pago no son válidos."), 400

    token = payment_data.get("token")
    method = payment_data.get("payment_method_id")
    installments = payment_data.get("installments")
    payer = payment_data.get("payer")
    issuer_id = payment_data.get("issuer_id")
    if (
        not isinstance(token, str)
        or not token
        or len(token) > 3000
        or not isinstance(method, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,50}", method)
        or isinstance(installments, bool)
        or not isinstance(installments, int)
        or not 1 <= installments <= 36
        or not isinstance(payer, dict)
        or (
            issuer_id is not None
            and (
                not isinstance(issuer_id, (str, int))
                or not str(issuer_id).isdigit()
                or len(str(issuer_id)) > 20
            )
        )
    ):
        return jsonify(error="Completa los datos de pago en el formulario seguro."), 400

    order = store_order_status(order_id)
    if order is None:
        return jsonify(error="No se encontró el pedido de prueba."), 404
    if order["status"] in {"approved", "refunded", "rejected", "cancelled", "simulated"}:
        return jsonify(error="Este pedido ya no admite otro intento de pago."), 409

    try:
        payment = create_mercadopago_brick_payment(
            order,
            {
                "token": token,
                "payment_method_id": method,
                "installments": installments,
                "payer": payer,
                "issuer_id": issuer_id,
            },
            configuration,
        )
    except RuntimeError as error:
        app.logger.error("No se pudo procesar el pago de prueba: %s", error)
        return jsonify(error=str(error)), 502

    payment_id = payment.get("id")
    provider_status = payment.get("status")
    expected_statuses = {
        "approved": "approved",
        "pending": "pending",
        "in_process": "pending",
        "rejected": "rejected",
        "cancelled": "cancelled",
        "refunded": "refunded",
        "charged_back": "refunded",
    }
    amount = payment.get("transaction_amount")
    if (
        not isinstance(payment_id, (str, int))
        or not str(payment_id).isdigit()
        or payment.get("external_reference") != order_id
        or payment.get("currency_id") != "COP"
        or isinstance(amount, bool)
        or not isinstance(amount, (int, float))
        or round(amount) != order["total"]
        or payment.get("live_mode") is not False
        or provider_status not in expected_statuses
    ):
        app.logger.error("La respuesta de pago de prueba no coincide con el pedido.")
        return jsonify(error="No se pudo verificar el resultado del pago de prueba."), 502

    status = expected_statuses[provider_status]
    if not update_store_payment(order_id, str(payment_id), status):
        app.logger.error("No se pudo guardar el estado del pago de prueba.")
        return jsonify(error="No se pudo registrar el resultado del pago."), 503

    return jsonify(order_id=order_id, status=status, mode="test")


@app.post("/api/checkout")
def create_checkout():
    configuration = payment_test_configuration()
    if not configuration["ready"]:
        return jsonify(
            error=(
                "El checkout de prueba no está configurado. Se requieren credenciales TEST- "
                "de Mercado Pago, una URL HTTPS pública y el secreto de firma del webhook."
            )
        ), 503

    order, error = build_request(request.get_json(silent=True))
    if error:
        message, status = error
        return jsonify(error=message), status

    try:
        preference_id, checkout_url = create_mercadopago_preference(order, configuration)
        with REQUESTS_LOCK:
            save_checkout_payment(order, preference_id, checkout_url)
    except RuntimeError as error:
        app.logger.error("No se pudo preparar el checkout de prueba: %s", error)
        return jsonify(error=str(error)), 502
    except (OSError, sqlite3.Error, ValueError):
        app.logger.exception("No se pudo guardar el checkout de prueba.")
        return jsonify(error="No se pudo guardar el checkout de prueba."), 503

    return jsonify(
        request=order,
        checkout_url=checkout_url,
        provider="Mercado Pago",
        mode="test",
    ), 201


@app.get("/api/checkout/<request_id>")
def get_checkout_status(request_id):
    payment = checkout_payment_status(request_id)
    if payment is None:
        payment = store_order_status(request_id)
    if payment is None:
        return jsonify(error="No se encontró el estado del pago."), 404
    return jsonify(
        status=payment["status"],
        updated_at=payment["updated_at"].isoformat()
        if isinstance(payment["updated_at"], datetime)
        else payment["updated_at"],
    )


@app.post("/api/payments/webhook")
def mercadopago_webhook():
    configuration = payment_test_configuration()
    if not configuration["ready"]:
        return jsonify(error="El webhook de pagos no está configurado."), 503
    body = request.get_json(silent=True)
    data = body.get("data") if isinstance(body, dict) else None
    payment_id = request.args.get("data.id") or request.args.get("id")
    if not payment_id and isinstance(data, dict):
        payment_id = data.get("id")
    if not isinstance(payment_id, (str, int)) or not str(payment_id).isdigit():
        return jsonify(error="Notificación de pago inválida."), 400
    payment_id = str(payment_id)
    if not verify_mercadopago_signature(payment_id):
        return jsonify(error="Firma de Mercado Pago inválida."), 401

    try:
        payment = fetch_mercadopago_payment(payment_id, configuration["access_token"])
    except RuntimeError as error:
        return jsonify(error=str(error)), 502

    order_id = payment.get("external_reference")
    preference_id = payment.get("preference_id")
    if (
        str(payment.get("id", "")) != payment_id
        or not isinstance(order_id, str)
    ):
        return jsonify(error="El pago no está asociado a un pedido válido."), 400
    if payment.get("currency_id") != "COP":
        return jsonify(error="La moneda del pago no coincide con COP."), 400
    amount = payment.get("transaction_amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return jsonify(error="El importe informado por el proveedor no es válido."), 400
    if payment.get("status") not in {
        "approved", "pending", "in_process", "rejected", "cancelled", "refunded", "charged_back",
    }:
        return jsonify(error="El estado informado por el proveedor no es válido."), 400

    stored_payment = checkout_payment_status(order_id)
    store_payment = store_order_status(order_id) if stored_payment is None else None
    if stored_payment is not None:
        valid_payment = (
            preference_id == stored_payment["preference_id"]
            and round(amount) == stored_payment["total"]
            and payment.get("live_mode") is False
        )
    elif store_payment is not None:
        valid_payment = (
            round(amount) == store_payment["total"]
            and payment.get("live_mode") is False
        )
    else:
        valid_payment = False
    if not valid_payment:
        return jsonify(error="El importe, el entorno de prueba o el pedido no coinciden con el checkout."), 400

    status_mapping = {
        "approved": "approved",
        "rejected": "rejected",
        "cancelled": "cancelled",
        "refunded": "refunded",
        "charged_back": "refunded",
        "pending": "pending",
        "in_process": "pending",
    }
    updated = (
        update_checkout_payment(order_id, payment_id, status_mapping[payment["status"]])
        if stored_payment is not None
        else update_store_payment(order_id, payment_id, status_mapping[payment["status"]])
    )
    if not updated:
        return jsonify(error="No se pudo registrar el estado del pago."), 404
    return jsonify(received=True)


@app.post("/api/requests")
def create_request():
    created, error = build_request(request.get_json(silent=True))
    if error:
        message, status = error
        return jsonify(error=message), status
    with REQUESTS_LOCK:
        save_request(created)
    return jsonify(created), 201


@app.patch("/api/requests/<request_id>")
@admin_required
def update_request(request_id):
    body = request.get_json(silent=True)
    status = body.get("status") if isinstance(body, dict) else None
    if status not in VALID_STATUSES - {"pending"}:
        return jsonify(error="La decisión debe ser approved o rejected."), 400

    with REQUESTS_LOCK:
        target, error = decide_request(request_id, status)
        if error == "not_found":
            return jsonify(error="No se encontró la solicitud."), 404
        if error == "already_decided":
            return jsonify(error="Solo se pueden decidir solicitudes pendientes."), 409
    return jsonify(target)


@app.get("/api/admin/status")
def admin_status():
    configured_password = os.environ.get("NEXUS_ADMIN_PASSWORD", "")
    authenticated = (
        bool(session.get("nexus_admin"))
        and session.get("admin_expires_at", 0) >= int(time())
    )
    return jsonify(
        configured=len(configured_password) >= 16,
        authenticated=authenticated,
        csrf_token=session.get("csrf_token") if authenticated else None,
    )


@app.post("/api/admin/login")
def admin_login():
    configured_password = os.environ.get("NEXUS_ADMIN_PASSWORD", "")
    if len(configured_password) < 16:
        return jsonify(
            error="Define NEXUS_ADMIN_PASSWORD en el servidor con al menos 16 caracteres."
        ), 503

    body = request.get_json(silent=True)
    password = body.get("password") if isinstance(body, dict) else None
    source_ip = request.remote_addr or "unknown"
    now = monotonic()
    with ADMIN_LOGIN_LOCK:
        attempts = [attempt for attempt in ADMIN_LOGIN_ATTEMPTS.get(source_ip, []) if now - attempt < 300]
        ADMIN_LOGIN_ATTEMPTS[source_ip] = attempts
        if len(attempts) >= 5:
            return jsonify(error="Demasiados intentos. Espera cinco minutos antes de volver a intentar."), 429
        if (
            not isinstance(password, str)
            or len(password) > 256
            or not hmac.compare_digest(password, configured_password)
        ):
            attempts.append(now)
            ADMIN_LOGIN_ATTEMPTS[source_ip] = attempts
            return jsonify(error="La contraseña no es correcta."), 401
        ADMIN_LOGIN_ATTEMPTS.pop(source_ip, None)

    session.clear()
    session["nexus_admin"] = True
    session["csrf_token"] = secrets.token_urlsafe(32)
    session["admin_expires_at"] = int(time()) + 8 * 60 * 60
    return jsonify(authenticated=True, csrf_token=session["csrf_token"])


@app.post("/api/admin/logout")
@admin_required
def admin_logout():
    session.clear()
    return jsonify(authenticated=False)


@app.get("/health")
def health():
    if DATABASE_URL:
        with server_connection() as connection:
            initialize_server(connection)
            connection.execute("SELECT 1")
        database = "MySQL" if DATABASE_BACKEND == "mysql" else "PostgreSQL"
    else:
        with sqlite_connection() as connection:
            initialize_sqlite(connection)
            connection.execute("SELECT 1")
        database = "SQLite"
    return jsonify(status="ok", service="NEXUS Hardware", database=database)


@app.errorhandler(sqlite3.Error)
def sqlite_database_error(error):
    app.logger.error("Error de la base de datos SQLite: %s", error)
    return jsonify(error="No fue posible completar la operación en la base de datos."), 503


@app.errorhandler(MySQLDatabaseError)
def mysql_database_error(error):
    app.logger.error("Error de base de datos MySQL: %s", error)
    return jsonify(error=str(error)), 503


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
