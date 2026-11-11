# BuildCorp · Evaluación 3 de Desarrollo Backend

Sistema de arriendo y control de herramientas para obras de construcción. Proyecto 4 de INACAP.

- **Aplicación en AWS Academy:** [http://54.160.224.202/](http://54.160.224.202/)
- **Código y configuración:** [BuildCorp-EC2/](BuildCorp-EC2/)
- **Guía de instalación, despliegue y defensa:** [README del proyecto](BuildCorp-EC2/README.md)
- **Registro de apoyo de IA:** [prompts_ia.md](BuildCorp-EC2/prompts_ia.md)

La aplicación usa Django, Django REST Framework y PostgreSQL. Nginx recibe las solicitudes públicas y las reenvía a Gunicorn. PostgreSQL y Gunicorn escuchan en localhost dentro de la misma EC2.

## Reanudar BuildCorp en AWS Academy

1. Abre el **Learner Lab** y pulsa **Start Lab**. Cuando el indicador AWS esté verde, abre la consola desde el enlace **AWS**.
2. En **EC2 → Instancias**, selecciona **Norte de Virginia (`us-east-1`)**. Busca `BuildCorp-EVA3` (`i-0226953f2ce33aba0`). Si está detenida, selecciona **Estado de la instancia → Iniciar instancia** y espera a que figure **En ejecución**.
3. Selecciona **Conectar → EC2 Instance Connect → Conectar** como `ubuntu`. En la terminal de la instancia ejecuta:

   ```bash
   bash ~/buildcorp-reanudar.sh
   ```

   El script usa la IPv4 pública vigente para actualizar Django y Nginx, comprueba los servicios y muestra la URL de BuildCorp. Si la IP cambió, actualiza los enlaces de ambos README después de verificar la nueva URL.

4. Desde tu navegador, abre la URL pública que imprime el script y comprueba que carga BuildCorp. Añade `/gestion/` para abrir Django Admin. Para revisar los servicios y las migraciones en Ubuntu:

   ```bash
   cd /opt/buildcorp
   systemctl show postgresql.service buildcorp.service nginx.service --property=Id --property=ActiveState --no-pager
   .venv/bin/python manage.py showmigrations inventario
   ```

   Los tres servicios deben indicar `active` y las seis migraciones de inventario deben mostrar `[X]`. `buildcorp.service` ejecuta Gunicorn.

5. Al terminar la demostración, detén la instancia desde EC2 y cierra el laboratorio. Para configurar otra instancia desde cero, consulta la [guía de despliegue](BuildCorp-EC2/README.md#desplegar-en-ec2).

## Ejecutar en desarrollo

```bash
git clone https://github.com/MarceloDh/BuildCorp-Backend.git
cd BuildCorp-Backend/BuildCorp-EC2
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export DEBUG=1 DB_ENGINE=sqlite
python manage.py migrate
python manage.py crear_roles
python manage.py createsuperuser
python manage.py runserver
```

En Windows, activa el entorno con `.\.venv\Scripts\Activate.ps1` y asigna las variables con `$env:DEBUG="1"` y `$env:DB_ENGINE="sqlite"`. La guía del proyecto incluye el despliegue con PostgreSQL.

## Defensa

1. Abre el inventario y muestra los estados Disponible, En uso, Mantenimiento y Dado de baja.
2. Registra una entrega y una devolución con firmas ficticias y verifica el historial del préstamo.
3. Muestra un mantenimiento exigible por fecha y otro por horas acumuladas.
4. Deja vencer un préstamo, muestra la alerta y comprueba que el contratista queda bloqueado hasta devolverlo.
5. Muestra el Admin personalizado en `/gestion/`, su filtro por estado y la diferencia de permisos entre Bodega, Supervisión y Contratista. Define `ADMIN_PATH` en el entorno para cambiar la ruta.

La IP se asignó automáticamente. Si el laboratorio reinicia la EC2 y cambia la IP, actualiza `ALLOWED_HOSTS`, `server_name` en Nginx y los enlaces del repositorio. Para la demo HTTP usa exclusivamente datos ficticios.

## Evidencias del despliegue inicial

Las capturas corresponden al despliegue previo a la reanudación. La IP que aparece en ellas es histórica.

**EC2 en ejecución**

<img width="960" height="200" alt="clipboard" src="https://github.com/user-attachments/assets/f06366b1-6a62-47be-baab-7463d511dc91" />


**PostgreSQL y migraciones aplicadas**

<img width="570" height="190" alt="clipboard" src="https://github.com/user-attachments/assets/65fada77-25c8-435f-b9b4-bb75115786b9" />
