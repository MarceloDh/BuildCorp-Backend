# BuildCorp · Evaluación 4

BuildCorp gestiona obras, bodegas, herramientas y mantenimientos. La interfaz separada consume Django REST Framework con JSON y JWT. Los flujos de préstamos y traslados de EVA3 siguen disponibles en el proyecto Django.

## Ejecución local

En PowerShell, desde la raíz del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r BuildCorp-EC2/requirements.txt
$env:DEBUG = "1"
$env:DB_ENGINE = "sqlite"
$env:JWT_SIGNING_KEY = python -c "import secrets; print(secrets.token_hex(32))"
Set-Location BuildCorp-EC2
..\.venv\Scripts\python.exe manage.py migrate
..\.venv\Scripts\python.exe manage.py crear_roles
..\.venv\Scripts\python.exe manage.py createsuperuser
..\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

En otra terminal, desde la raíz:

```powershell
.\.venv\Scripts\python.exe -m http.server 5173 --bind 127.0.0.1 --directory frontend
```

Abre `http://127.0.0.1:5173/` y usa la cuenta local. Para PostgreSQL, cambia `DB_ENGINE` a `postgresql` y configura `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` y `DB_PASSWORD`. Repite migraciones y crea una cuenta en esa base. Ejecuta `manage.py test` para correr la suite. La cuenta de PostgreSQL de pruebas debe poder crear una base temporal.

## API v4

| Ruta bajo `/api/v4/` | Métodos | Acceso |
| --- | --- | --- |
| `token/` | POST | Usuario y contraseña |
| `token/refresh/` | POST | Token refresh vigente |
| `salud/` | GET | Público · empleado en la prueba de throttling |
| `perfil/` | GET | Bodega o Supervisión |
| `obras/`, `bodegas/`, `herramientas/`, `mantenimientos/` | GET, POST | GET para ambos roles, POST para Supervisión |
| `{colección}/{id}/` | GET, PUT, PATCH, DELETE | GET para ambos roles, escritura para Supervisión |
| `recursos/guia/` | GET | Bodega o Supervisión |

En las rutas protegidas envía `Authorization: Bearer <access>`. Para crear, envía JSON con los siguientes campos:

| Colección | Ejemplo |
| --- | --- |
| Obras | `{"nombre":"Obra piloto","direccion":"Santiago"}` |
| Bodegas | `{"nombre":"Bodega norte","obra":1}` |
| Herramientas | `{"codigo":"EVA4-001","nombre":"Taladro","bodega":1}` |
| Mantenimientos | `{"activo":1,"tarea":"Revisar brocas","horas_limite":60}` |

Los IDs de relación corresponden a las respuestas reales de las altas. Los cambios de obra, destino y herramienta asociada se rigen por el dominio. Los mantenimientos completados conservan su historial. Las pruebas cubren HTTP 200, 201, 204, 400, 401, 403, 404 y 409.

## AWS Academy

La [plantilla CloudFormation](infra/aws-eva4.yml) crea los recursos temporales en `us-east-1`. La HTTP API de mismo origen entrega la interfaz y la API por HTTPS. Un ALB interno dirige `/api/v4/*` al backend y las rutas de interfaz a la otra EC2. Se reutiliza `LabInstanceProfile`, ya que el laboratorio restringe la creación de roles. Las EC2 permiten HTTP entrante solo desde el ALB y se administran mediante SSM. Sus IPv4 asignadas permiten instalar dependencias sin NAT Gateway. RDS está en subredes privadas y permite 5432 desde el grupo del backend. La instalación usa TLS `verify-full`, un usuario PostgreSQL propio y un archivo local de variables protegido.

En CloudShell copia el repositorio y, desde su raíz, crea un paquete de código sin datos locales. Necesitas AWS CLI y jq.

```bash
work=$(mktemp -d)
umask 077
tar -czf "$work/buildcorp-eva4.tar.gz" \
  --exclude='*/.venv' --exclude='*/.env' --exclude='*/__pycache__' \
  --exclude='*/staticfiles' --exclude='*.sqlite3' --exclude='*.pem' --exclude='*.key' \
  BuildCorp-EC2 frontend
openssl rand -hex 24 > "$work/clave-demo"
bash infra/desplegar-lab.sh buildcorp-eva4 "$work/buildcorp-eva4.tar.gz" "$work/clave-demo"
```

El instalador configura dos cuentas ficticias. `supervision_demo` administra y `bodega_demo` consulta. La contraseña temporal queda en `$work/clave-demo`. Para retomar una instalación fallida, revisa primero los eventos de CloudFormation y las salidas de SSM en el mismo stack. El ARN del secreto maestro de RDS no contiene su valor. Mantén contraseñas y tokens fuera de capturas y entregables.

### Validación y capturas

1. **EC2 y aplicación.** Anota los IDs de frontend y backend y verifica los dos targets saludables. En la URL HTTPS del stack inicia sesión, crea las cuatro entidades y edita una herramienta. Captura el HTTP 200 o 201 y la fila en RDS con el mismo código.
2. **Gateway.** Comprueba `/api/v4/salud` y el límite de 2 solicitudes/s con ráfaga de 5. API Gateway expone la ruta sin barra final y la reescribe a `/api/v4/salud/` para Django. En CloudShell prueba solo esa ruta de la pila:

   ```bash
   export URL=$(aws cloudformation describe-stacks --stack-name buildcorp-eva4 \
     --query 'Stacks[0].Outputs[?OutputKey==`Url`].OutputValue | [0]' --output text)
   seq 1 20 | xargs -P 10 -I{} curl -sS -o /dev/null -w '%{http_code}\n' "$URL/api/v4/salud" | sort | uniq -c
   ```

3. **RDS.** Captura configuración de cifrado, `PubliclyAccessible=false`, regla de ingreso TCP 5432 y retención. Desde la conexión real de Django comprueba TLS mediante `SELECT ssl, version FROM pg_stat_ssl WHERE pid = pg_backend_pid();`.
4. **S3.** Captura Block Public Access, SSE-S3 y el objeto. Inicia la descarga desde la interfaz con una cuenta autorizada. Oculta el query firmado en las capturas.
5. **CloudWatch.** Captura CPUUtilization de la EC2 backend y la alarma a 70% en dos períodos de 300 segundos. La alarma apunta a un tema SNS. Una entrega por correo requiere suscripción confirmada.
6. **Respaldo.** Captura la ventana de retención y crea el snapshot `buildcorp-eva4-demostracion` desde la instancia `buildcorp-eva4-pg`, si el laboratorio lo permite. Espera el estado `available` antes de obtener la evidencia. Para recuperación restaurarías una instancia nueva, validarías el contenido y cambiarías el endpoint.
7. **Análisis.** Ejecuta SonarScanner desde la raíz con el `sonar-project.properties` existente y `SONAR_HOST_URL` y `SONAR_TOKEN` en el entorno. En ZAP usa exploración pasiva sobre la URL propia del stack y registra rutas, alertas y límites. Si analizas respuestas autenticadas, utiliza solo una cuenta ficticia y elimina tokens del informe.
8. **Cierre.** Guarda las capturas localmente. Con autorización para retirar la pila de demostración ejecuta `bash infra/limpiar-lab.sh buildcorp-eva4` y espera la confirmación. Verifica en la región que desaparecieron los recursos de EVA4, incluyendo el snapshot, el grupo de logs y el tema SNS. Conserva los recursos anteriores fuera de esta pila.
