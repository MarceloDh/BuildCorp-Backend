# BuildCorp

Evaluación 3 de Desarrollo Backend. Aplicación para controlar herramientas, préstamos y mantenimientos en bodegas de obra.

**URL pública verificada el 11 de noviembre de 2026:** [http://54.160.224.202/](http://54.160.224.202/). La instancia `BuildCorp-EVA3` (`i-0226953f2ce33aba0`) está en `us-east-1`. Tras detenerla e iniciarla, consulta la nueva IP y actualiza `ALLOWED_HOSTS`, `server_name` en Nginx y la URL en ambos README.

## Ejecutar en Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
$env:DEBUG = "1"
$env:DB_ENGINE = "sqlite"
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py crear_roles
.\.venv\Scripts\python manage.py createsuperuser
.\.venv\Scripts\python manage.py runserver
```

Abre [http://127.0.0.1:8000/](http://127.0.0.1:8000/). La configuración de ejemplo usa SQLite para desarrollo. Para usar PostgreSQL local, configura `DB_ENGINE=postgresql` y completa los datos de conexión en `.env`.

```powershell
.\.venv\Scripts\python manage.py test
```

## Cuentas y operación

- **Portada pública** en `/`. Presenta BuildCorp y da acceso al inicio de sesión.
- **Ayuda al cliente** en la portada. Incluye una guía de arriendo, preguntas frecuentes y acceso al historial. El catálogo permite filtrar servicios por categoría y la cuenta filtra préstamos por estado.
- **Errores públicos** con el gato esfinge y enlaces de regreso. Las rutas y registros inexistentes devuelven 404, los accesos restringidos y formularios vencidos devuelven 403. La página de error del servidor funciona sin consultar la base de datos. Las respuestas de error de la API siguen siendo JSON.
- **Catálogo público** en `/catalogo/`. Supervisión decide qué mostrar desde la ficha de cada herramienta. El catálogo muestra nombres de equipos publicados y activos. La disponibilidad se confirma con bodega.
- **Servicios de arriendo** guardados en PostgreSQL. El catálogo incluye trece tipos iniciales y Supervisión puede editar o agregar servicios. Cada herramienta física se vincula a su servicio desde la ficha de inventario. El buscador sugiere servicios y equipos publicados mientras escribes.
- **Contratación con cuenta**. Se exigen nombre, apellido, correo, teléfono, fecha y dirección con comuna y región. El registro público solicita los datos de contacto y ubicación. En cada contratación se precargan esos datos y puedes modificarlos para esa solicitud. El pago sigue siendo de prueba.
- **RUT y documentos**. El registro y la contratación validan el RUT con su dígito verificador. El cliente elige Webpay o transferencia y el medio queda guardado en la solicitud. El informe PDF se descarga desde su detalle. Para factura se exigen razón social, RUT, giro y dirección de facturación, y se muestra el desglose de neto e IVA incluido. Se usa un IVA de ejemplo del 19%. Los PDF están rotulados como demostración académica sin validez tributaria. [Tasa del IVA según SII](https://www.sii.cl/preguntas_frecuentes/impuestos_mensuales/001_130_0572.htm)
- **Stock por unidad**. Una solicitud aprobada asigna y reserva una herramienta física disponible. No cuenta como disponible si está prestada, reservada, dada de baja o tiene mantenimiento en curso o exigible. La reserva comienza al confirmar, incluso si la fecha solicitada es futura, y continúa hasta entrega o cancelación. La entrega con firma la convierte en préstamo. Al devolverla vuelve a estar disponible si no corresponde mantenimiento. Los servicios logísticos se coordinan por visita o viaje.
- **Bloqueo manual**. Supervisión puede editar un contratista y activar **Bloqueado por administración**, indicando un motivo. El servidor impide nuevas reservas y entregas a esa persona. También bloquea automáticamente por devoluciones vencidas. El cliente conserva acceso al historial para regularizar su situación.
- **Contratista** entra a `/mi-cuenta/` para consultar sus préstamos, sus detalles, plazos y avisos de bloqueo. La entrega y devolución se registran en bodega.
- **Bodega** consulta el inventario, firma entregas y devoluciones y ve las alertas.
- **Supervisión** también administra obras, bodegas, contratistas y herramientas. Puede trasladar, dar de baja, reactivar y programar o cerrar mantenimientos.
- **Superusuario** tiene acceso a gestión interna. Con la configuración de ejemplo entra por `/gestion/`, crea cuentas de personal y asígnales el grupo correspondiente. Los movimientos históricos se consultan en gestión. Las transiciones se ejecutan desde las pantallas de operación en `/bodega/` y sus secciones.

El cliente puede crear su cuenta desde `/registro/`, incluso si está usando una sesión de prueba. El formulario avisa que al crear la cuenta iniciará sesión con ella. Para vincular una cuenta a un contratista ya registrado, crea un usuario activo sin permisos de personal ni grupos operativos en gestión interna y asígnalo en **Cuenta de acceso**. Cada cliente ve exclusivamente sus solicitudes, documentos y préstamos.

Para practicar localmente con inventario ficticio ejecuta `python manage.py cargar_inventario_demo`. Agrega dos unidades por tipo de equipo en una bodega de demostración y puede repetirse sin duplicarlas. En la instancia de entrega puedes registrar las unidades reales desde las plantillas. Las migraciones cargan las tarifas iniciales de ejemplo, sin crear cuentas ni herramientas.

En **Solicitudes** el personal puede abrir la reserva y pulsar **Registrar entrega con firma**. La devolución se registra desde el préstamo vinculado. Cancelar una solicitud aún pendiente libera su unidad. Una solicitud entregada requiere devolución para liberar el equipo.

La firma es un trazo manuscrito capturado en pantalla, asociado al responsable, la cuenta que registra y la fecha. El atraso se calcula sobre préstamos abiertos al momento de consultar o intentar una entrega. El bloqueo desaparece al devolver el último préstamo vencido. Los mantenimientos se marcan por realizar cuando se cumple la fecha o el umbral de horas, lo que ocurra primero.

La API JSON exige sesión de Bodega o Supervisión. Las rutas de consulta son `/api/herramientas/`, `/api/prestamos/`, `/api/mantenimientos/` y `/api/traslados/`. Los formularios web realizan las operaciones de escritura. Si defines `APP_PREFIX`, las rutas web, API y de gestión quedan bajo ese prefijo. `ADMIN_PATH` permite configurar el segmento de gestión. La IP o DNS permitido se configura con `ALLOWED_HOSTS`.

## Reanudar la instancia existente

Para iniciar la EC2 de la evaluación, ajustar la IP y comprobar el servicio, sigue [los pasos de reanudación del README principal](../README.md#reanudar-buildcorp-en-aws-academy).

## Desplegar en EC2

Esta secuencia reproduce el despliegue inicial de BuildCorp en una EC2 Ubuntu de AWS Academy. En el grupo de seguridad habilita SSH (22) desde tu IP y HTTP (80) para la demostración. PostgreSQL y Gunicorn escuchan en localhost. Si la instancia ya está configurada, usa [Reanudar la instancia existente](#reanudar-la-instancia-existente).

### 1. Instalar paquetes y copiar el proyecto

```bash
sudo apt-get update
sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y git unzip python3-venv postgresql nginx
git clone https://github.com/MarceloDh/BuildCorp-Backend.git ~/buildcorp-repo
sudo install -d -o ubuntu -g ubuntu /opt/buildcorp
cp -a ~/buildcorp-repo/BuildCorp-EC2/. /opt/buildcorp/
cd /opt/buildcorp
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

### 2. Crear la base de datos y configurar Django

```bash
sudo -u postgres createuser --pwprompt buildcorp
sudo -u postgres createdb --owner=buildcorp buildcorp
touch .env
chmod 600 .env
openssl rand -hex 48
nano .env
```

Usa la contraseña que acabas de elegir y el valor generado por OpenSSL. Sustituye los marcadores y guarda el archivo solo en la instancia.

```dotenv
DEBUG=0
SECRET_KEY=CLAVE_GENERADA
ALLOWED_HOSTS=IP_PUBLICA,127.0.0.1,localhost
ADMIN_PATH=gestion
HTTPS=0
DB_ENGINE=postgresql
DB_NAME=buildcorp
DB_USER=buildcorp
DB_PASSWORD=CONTRASENA_ELEGIDA
DB_HOST=127.0.0.1
DB_PORT=5432
```

En el despliegue original el script generó ambos secretos en la EC2 y creó la base mediante `psql`. Aquí los comandos interactivos permiten reproducir esa misma configuración sin publicar secretos. Para la demostración HTTP usa datos y firmas ficticios.

### 3. Aplicar migraciones y preparar la aplicación

```bash
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py migrate --check
.venv/bin/python manage.py crear_roles
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py createsuperuser
```

El último comando permite crear una cuenta de administración para la demostración.

### 4. Configurar Gunicorn y Nginx

Reemplaza `IP_PUBLICA` por la IPv4 que muestra EC2.

```bash
IP_PUBLICA=REEMPLAZAR_CON_IPV4
sudo install -m 644 deploy/buildcorp.service /etc/systemd/system/buildcorp.service
sed "s/REEMPLAZAR_IP_O_DNS/${IP_PUBLICA}/" deploy/nginx.conf | sudo tee /etc/nginx/sites-available/buildcorp >/dev/null
sudo ln -sfn /etc/nginx/sites-available/buildcorp /etc/nginx/sites-enabled/buildcorp
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable buildcorp
sudo systemctl restart buildcorp
sudo systemctl reload nginx
```

### 5. Verificar el despliegue

```bash
sudo systemctl is-active postgresql buildcorp nginx
.venv/bin/python manage.py showmigrations inventario
.venv/bin/python manage.py shell -c 'from django.db import connection; connection.ensure_connection(); print(connection.vendor, connection.pg_version)'
curl -fsS -H "Host: ${IP_PUBLICA}" http://127.0.0.1/ -o /dev/null
```

Los tres servicios deben mostrar `active`, las seis migraciones deben aparecer con `[X]` y la comprobación de Django debe mostrar `postgresql` y su versión. Desde tu computador, abre `http://IP_PUBLICA/` y `http://IP_PUBLICA/gestion/`. Las [capturas del despliegue inicial](../README.md#evidencias-del-despliegue-inicial) están en el README principal.

### Opciones de instalación

Si el código se entrega como ZIP, puedes copiarlo desde tu computador y extraerlo en Ubuntu después de crear `/opt/buildcorp`:

```powershell
scp -i "RUTA_LLAVE.pem" .\BuildCorp-EC2.zip ubuntu@IP_PUBLICA:~/
```

```bash
unzip ~/BuildCorp-EC2.zip -d /opt/buildcorp
```

Para HTTPS, habilita el puerto 443, configura TLS en Nginx y establece `HTTPS=1` y `CSRF_TRUSTED_ORIGINS=https://TU_DOMINIO`. Puedes comprobar los ajustes de producción con `.venv/bin/python manage.py check --deploy`. En la demostración por HTTP pueden aparecer avisos de HTTPS y HSTS. Si defines `APP_PREFIX`, incluye el prefijo en las URLs de acceso y del panel.

## Verificación antes de entregar

En una base de pruebas PostgreSQL 16.2, se aplicaron las seis migraciones de `inventario`. Pasaron las 16 pruebas de Django, incluidas las pruebas de concurrencia de reservas y entregas. Para repetirlas, usa una base PostgreSQL de desarrollo y un rol de pruebas que pueda crear una base temporal:

```bash
python manage.py makemigrations --check --dry-run
python manage.py test -v 2
```

En EC2, después de migrar, registra la evidencia de PostgreSQL sin mostrar el archivo `.env`:

```bash
.venv/bin/python manage.py showmigrations inventario
sudo -u postgres psql -d buildcorp -c "SELECT current_database(), current_setting('server_version');"
sudo -u postgres psql -d buildcorp -c "SELECT name, applied FROM django_migrations WHERE app = 'inventario' ORDER BY name;"
```

En el navegador, usa cuentas y firmas de demostración. Guarda una captura de la instancia en ejecución, la salida anterior, la portada con su IP visible, el Admin con sus filtros y los resultados de cada flujo. Si cambias `ADMIN_PATH` o `APP_PREFIX`, reinicia `buildcorp` para que Gunicorn cargue los valores nuevos.

## Prueba para la defensa

1. Crea una obra con dos bodegas, un contratista y dos herramientas. Traslada una y muestra el registro del movimiento.
2. Programa una revisión a las 5 horas acumuladas y entrega esa herramienta con firma.
3. Para demostrar morosidad en pocos minutos, registra la entrega con un vencimiento uno o dos minutos en el futuro. Después del vencimiento, recarga el resumen y prueba un segundo préstamo para ese contratista.
4. Registra la devolución con firma y 5 horas de uso. Comprueba que el contratista se desbloqueó, que apareció la revisión pendiente y que la herramienta no puede prestarse hasta hacer el mantenimiento.
5. Inicia y completa el mantenimiento por horas. En otra herramienta, programa una revisión con fecha límite de hoy y muestra que ya corresponde realizarla. Da de baja una herramienta sin operaciones pendientes y muestra el cuarto estado del inventario.
6. Abre Django Admin con un superusuario y muestra la marca BuildCorp, la búsqueda por código y los filtros de estado. Con una cuenta de Bodega, demuestra que puede registrar entregas pero no crear herramientas. Con una cuenta de contratista, muestra que solo puede ver sus propios préstamos.
7. Cierra explicando que Nginx recibe la petición pública, Gunicorn ejecuta Django y el ORM guarda los registros en PostgreSQL dentro de la misma EC2. Muestra las migraciones aplicadas y vuelve a abrir un préstamo para enseñar las dos firmas persistidas.

## Arquitectura 4+1

| Vista | BuildCorp |
| --- | --- |
| Lógica | Las obras contienen bodegas. Cada herramienta tiene una bodega actual, préstamos, mantenimientos e historial de traslados. |
| Desarrollo | `buildcorp` contiene configuración y rutas. `inventario` agrupa modelos, servicios, formularios, vistas web y API. |
| Procesos | Los servicios de entrega, devolución, traslado y mantenimiento usan transacciones. PostgreSQL bloquea la fila de la herramienta durante cada cambio y aplica restricciones de unicidad. |
| Física | Navegador → Nginx → Gunicorn → PostgreSQL. La aplicación y la base viven en la misma EC2. |
| Escenario | Al devolver una herramienta vencida, se conserva el registro, se actualizan las horas y se comprueba si corresponde mantenimiento. Si era el último atraso, el contratista puede recibir otro préstamo. |
