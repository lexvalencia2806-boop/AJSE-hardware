# NEXUS Hardware — Proyecto Final

**Estudiante:** Emanuel Segura Valencia  
**Institución:** Politécnico Superior de Occidente  
**Área:** Desarrollo web · Semestre 2  
**Presentado a:** Profesor Dioni Rodallega Murillo

NEXUS Hardware es una tienda de una sola página con catálogo, carrito y checkout de demostración. Sin credenciales, registra pedidos simulados; con Mercado Pago configurado explícitamente, permite transacciones Sandbox mediante Card Payment Brick. No vende inventario real ni procesa cobros reales. El catálogo tiene datos de referencia, no existencias verificadas. Su lema es **“Tecnología que conecta ideas, impulsa talento y transforma el mañana”**.

## Abrir el proyecto

### Backend y frontend

1. Instala Python 3.10 o posterior.
2. Abre esta carpeta en Visual Studio Code.
3. Haz doble clic en `iniciar.bat` para instalar las dependencias e iniciar el servidor.
4. Abre **http://127.0.0.1:5000** en el navegador.
5. Para detener el servidor, vuelve a la ventana de comandos y presiona `Ctrl+C`.

La interfaz y sus estilos no dependen de fuentes de CDN. Las imágenes externas del catálogo tienen una ilustración local de respaldo. El catálogo funciona en modo local con `localStorage` cuando se sirve con Live Server; para guardar solicitudes compartidas entre sesiones, inicia el backend Flask.

También puedes iniciar el servidor desde una terminal:

```powershell
python -m pip install -r requirements.txt
python app.py
```

### Base de datos SQLite

El backend guarda solicitudes y sus productos en una base de datos SQLite real y persistente en `data/nexus.sqlite3`. Python incluye SQLite, así que no necesitas instalar ni iniciar un servidor de base de datos. Las tablas, claves foráneas, restricciones e índices se crean automáticamente al usar la API. La base queda en este equipo; no es un servicio en la nube ni sincroniza datos entre varias computadoras.

Para guardar la base en otra ubicación, define `NEXUS_DATABASE_PATH` antes de iniciar Flask:

```powershell
$env:NEXUS_DATABASE_PATH = "C:\datos\nexus.sqlite3"
python app.py
```

Si existe `data/requests.json` de una versión anterior, las solicitudes se importan una sola vez a SQLite y el archivo original se conserva.

### MySQL opcional

NEXUS puede guardar sus pedidos y pagos en MySQL. Primero crea una base de datos vacía dedicada a NEXUS desde MySQL Workbench o la consola:

Ejecuta este SQL en el editor de consultas de MySQL Workbench (no en PowerShell):

```sql
CREATE DATABASE nexus_hardware CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

No uses `libreria_db`: sus tablas (`Libros`, `Clientes`, `Ventas`) pertenecen a la librería y no son las tablas de la tienda de hardware. NEXUS solo crea sus propias tablas dentro de la base que especifiques; no modifica ni borra las tablas de la librería.

Instala las dependencias e inicia Flask con la URL de conexión de MySQL:

```powershell
python -m pip install -r requirements.txt
$env:DATABASE_URL = "mysql://USUARIO:CONTRASEÑA@127.0.0.1:3306/nexus_hardware"
python app.py
```

Sustituye `USUARIO` y `CONTRASEÑA` por las credenciales del usuario MySQL que tenga permiso sobre `nexus_hardware`. Si la contraseña tiene caracteres especiales, codifícala para URL (por ejemplo, `@` como `%40`). En PowerShell, esa variable solo afecta a la ventana actual. La URL contiene la contraseña: no la publiques, no la guardes en el código y no la compartas por el chat.

Al iniciar, NEXUS ejecuta `data/schema.mysql.sql` y crea las tablas de solicitudes, productos de pedido y pagos si no existen. Comprueba la conexión en `http://127.0.0.1:5000/health`; debe indicar `"database":"MySQL"`. Con `DATABASE_URL` configurada, MySQL tiene prioridad sobre SQLite. Si usas PostgreSQL, su esquema sigue en `data/schema.sql`.

### Solo frontend con Live Server

Abre `index.html` en Visual Studio Code y selecciona **Open with Live Server**. Sin el backend, el catálogo funciona en modo de demostración y los datos se guardan en el almacenamiento local de ese navegador.

Si Flask también está iniciado, Live Server se conecta a `http://127.0.0.1:5000` y las solicitudes se guardan en SQLite o en la base de servidor indicada por `DATABASE_URL` (MySQL o PostgreSQL). La pastilla superior muestra si se está usando el **Backend Python** o el modo **Demo local**.

## Usar la tienda

1. Explora el catálogo. Cada precio y disponibilidad están marcados como referenciales y no verificados con un proveedor.
2. Agrega referencias al carrito y selecciona **Comprar en NEXUS**.
3. Sin credenciales Sandbox de Mercado Pago, el checkout funciona en **modo de demostración**: pide los datos de entrega, registra un pedido simulado en **Solicitudes** y muestra una confirmación con número de pedido. No cobra dinero, no reserva inventario y no genera envío. Al cerrar y volver a abrir el checkout se conserva la confirmación.
4. Solo cuando el servidor tiene habilitado explícitamente el entorno de pruebas y las credenciales `TEST-` requeridas, se muestra el Brick de tarjeta de Mercado Pago Sandbox. Los datos de tarjeta se tokenizan en el Brick oficial y no se guardan en NEXUS.
5. El resultado es una transacción Sandbox: no cobra dinero, no reserva existencias y no inicia un envío. Para una venta real, se requiere primero resolver inventario/proveedor y obligaciones comerciales.
6. **NEXUS Copilot** responde localmente sobre el catálogo. Gemini puede configurarse en el servidor para preguntas generales; ninguna IA garantiza responder correctamente a cualquier pregunta.

## Qué incluye

- Catálogo de 34 referencias en 8 categorías, incluidos 17 componentes para plataformas AMD AM4/AM5 e Intel LGA1700.
- Búsqueda, categorías, filtros de orden y tarjetas adaptables a móvil.
- Ficha por producto con plataforma, especificaciones, compatibilidad e instrucciones.
- Carrito local con cantidades y subtotales referenciales.
- Checkout de una sola página con datos de entrega, Mercado Pago Card Payment Brick y tokenización gestionada por Mercado Pago.
- Persistencia de órdenes y datos de entrega para revisión administrativa protegida.
- Panel de aprobaciones con filtros y resumen; solo las solicitudes pendientes se pueden decidir.
- Backend REST en Flask con validación de cantidades y del cliente y cálculo del total desde el catálogo del servidor.
- Persistencia transaccional de solicitudes y productos en SQLite por defecto, MySQL o PostgreSQL opcional.
- Modo local de demostración con `localStorage` para probar la interfaz sin iniciar Python.
- Recomendaciones locales y respuestas de ayuda sobre la tienda sin claves externas. Gemini se puede activar opcionalmente desde el servidor para preguntas generales.
- Experiencia de una sola página y funcionamiento local sin fuentes ni imágenes de CDN.
- Panel administrativo protegido por contraseña, sesión con caducidad, token CSRF y límite de intentos de acceso.
- Procesamiento de pago y webhooks de Mercado Pago exclusivamente en modo de prueba (`TEST-`); cobros de producción están deshabilitados.

## Límites de la demostración

El checkout integrado es Sandbox, no venta real. Las cantidades `stock`, precios y calificaciones del catálogo son datos de demostración, no están sincronizados y no deben presentarse como disponibilidad o importe final. El servidor rechaza pagos que no sean de prueba.

En el proyecto no hay prueba de inventario propio, contrato con proveedor, publicaciones verificadas, credenciales de Mercado Pago ni políticas comerciales. Antes de activar ventas reales se necesita acreditar inventario o autorización de reventa, sincronizar disponibilidad y precios, crear términos de compra y privacidad, definir impuestos, entregas, devoluciones y atención al cliente. El backend deliberadamente no admite credenciales ni pagos de producción.

La conexión con Gemini necesita una clave privada propia en el servidor. Sin ella, el asistente local no es una IA generativa y limita sus respuestas al catálogo y a la información de esta demostración. Ninguna configuración puede garantizar respuestas correctas a literalmente cualquier pregunta.

## Configurar el checkout Sandbox

El checkout interno solo se habilita con una cuenta de vendedor de prueba de Mercado Pago y después de activar conscientemente el indicador Sandbox. No uses credenciales `APP_USR-` ni compartas secretos.

1. En las herramientas de desarrollador de Mercado Pago, crea una aplicación de prueba y copia su **clave pública TEST-**, **Access Token TEST-** y **secreto de firma de notificaciones**. Crea usuarios compradores y vendedor de prueba.
2. Despliega el backend en HTTPS y configura la URL pública para que Mercado Pago pueda enviar webhooks a `/api/payments/webhook`. No uses localhost como URL de notificación.
3. En PowerShell, configura las variables antes de iniciar Flask:

   ```powershell
   $env:NEXUS_SECRET_KEY = (& python -c "import secrets; print(secrets.token_urlsafe(48))")
   $env:NEXUS_ADMIN_PASSWORD = "usa-una-contraseña-larga-propia"
   $env:NEXUS_STORE_TEST_ENABLED = "true"
   $env:NEXUS_PAYMENT_MODE = "test"
   $env:MERCADOPAGO_PUBLIC_KEY = "TEST-tu-clave-publica"
   $env:MERCADOPAGO_ACCESS_TOKEN = "TEST-tu-access-token"
   $env:MERCADOPAGO_WEBHOOK_SECRET = "tu-secreto-de-firma"
   $env:NEXUS_PUBLIC_URL = "https://tu-dominio"
   $env:NEXUS_COOKIE_SECURE = "true"
   python app.py
   ```

4. Abre **Comprar en NEXUS**. La pantalla informa qué requisito falta; solo cuando estén completos se muestra el formulario de dirección y el Brick de tarjeta de prueba.
5. Ejecuta pagos únicamente con los compradores y tarjetas de prueba de Mercado Pago. Comprueba el estado recibido por webhook en **Aprobaciones**.

No pongas claves en JavaScript, HTML, archivos versionados o en el chat. Usa un gestor de secretos del alojamiento al desplegar. El estado `/api/store/status` nunca devuelve el Access Token ni el secreto webhook. `NEXUS_STORE_TEST_ENABLED` no activa ventas reales: el backend valida que credenciales, pagos y webhooks pertenezcan a Sandbox. No existe una variable para activar cobros de producción.

## Configurar la administración

1. Define una contraseña administrativa larga y una clave de firma de sesión. No las guardes en `app.py`, JavaScript, Git ni en el chat:

   ```powershell
   $env:NEXUS_SECRET_KEY = (& python -c "import secrets; print(secrets.token_urlsafe(48))")
   $adminPassword = (& python -c "import secrets; print(secrets.token_urlsafe(24))")
   $env:NEXUS_ADMIN_PASSWORD = $adminPassword
   Write-Host "Guarda esta contraseña en tu gestor: $adminPassword"
   python app.py
   ```

   Guarda la contraseña en un gestor de contraseñas. En despliegues HTTPS, configura también `NEXUS_COOKIE_SECURE=true`.

## Archivos principales

| Archivo | Función |
| --- | --- |
| `index.html` | Estructura de las pantallas y formularios. |
| `static/styles.css` | Diseño y adaptación móvil. |
| `static/app.js` | Catálogo, carrito, navegación, recomendaciones y consumo de la API. |
| `static/products.json` | Catálogo de productos, precios e imágenes. |
| `data/schema.sqlite.sql` | Tablas, restricciones e índices de SQLite. |
| `data/schema.sql` | Tablas e índices para PostgreSQL opcional. |
| `data/schema.mysql.sql` | Tablas e índices para MySQL opcional. |
| `data/nexus.sqlite3` | Base de datos SQLite persistente, creada automáticamente. |
| `app.py` | API Flask y persistencia de solicitudes. |
| `requirements.txt` | Dependencias de Python. |
| `iniciar.bat` | Instalación y arranque rápido en Windows. |

## API del backend

| Método y ruta | Acción |
| --- | --- |
| `GET /api/products` | Devuelve el catálogo. |
| `GET /api/requests` | Devuelve solicitudes solo tras autenticar al administrador. |
| `POST /api/requests` | Valida y registra una solicitud como pendiente. |
| `PATCH /api/requests/<id>` | Registra la aprobación o el rechazo de una solicitud pendiente; requiere sesión administrativa y token CSRF. |
| `GET /api/admin/status` | Informa si la administración está configurada y si hay una sesión válida. |
| `POST /api/admin/login` y `/api/admin/logout` | Inicia o termina la sesión de administración. |
| `GET /api/store/status` | Informa si el Card Payment Brick Sandbox está listo, sin revelar secretos. |
| `POST /api/store/orders` | Crea una orden de prueba con el precio calculado desde el catálogo. |
| `POST /api/store/payments` | Procesa el token de tarjeta de prueba con Mercado Pago y monto del servidor. |
| `GET /api/ai/status` | Informa si el asistente Gemini está configurado, sin exponer la clave. |
| `POST /api/ai/chat` | Envía una conversación breve y el catálogo a Gemini desde el servidor. |
| `GET /health` | Comprueba que el backend esté funcionando. |

## Activar NEXUS Copilot

El chat generativo utiliza Gemini. La clave es opcional y debe guardarse como variable de entorno del servidor; nunca la pegues en `index.html`, `static/app.js` ni en un repositorio.

1. Crea una clave de Gemini en Google AI Studio.
2. En PowerShell, desde la carpeta del proyecto, ejecuta el lanzador:

   ```powershell
   .\iniciar_nexus.ps1
   ```

   El lanzador pide la clave en un campo oculto, la mantiene solo durante esa ejecución y la elimina del entorno al detener Flask con `Ctrl+C`. No la pegues en el chat ni la guardes en archivos. Si PowerShell bloquea el script, habilita la ejecución solo en esa ventana y vuelve a iniciarlo:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
   .\iniciar_nexus.ps1
   ```

   El servidor usa `gemini-2.5-flash` de forma predeterminada. Para usar otro modelo, define `GEMINI_MODEL`.
3. Abre la página y selecciona **Hablar con NEXUS Copilot**.

Cuando Gemini está configurado, puedes preguntarle sobre temas generales además del catálogo; no incluyas datos personales. Se le indica que responda directamente, no invente datos y reconozca cuando no está seguro, pero una IA puede equivocarse y no garantiza responder correctamente a todo. Las afirmaciones sobre productos, precios y disponibilidad de NEXUS se limitan al catálogo local. Sin clave, el chat solo orienta sobre el catálogo y el proceso de demostración.

## Pruebas del backend

Con Flask instalado, ejecuta desde la carpeta del proyecto:

```powershell
python -m unittest discover -s tests -v
```
