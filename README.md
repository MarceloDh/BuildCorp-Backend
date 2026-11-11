# BuildCorp · Evaluación 3 de Desarrollo Backend

Sistema de arriendo y control de herramientas para obras de construcción. Proyecto 4 de INACAP.

- **Aplicación en AWS Academy:** [http://98.90.198.186/](http://98.90.198.186/)
- **Código y configuración:** [BuildCorp-EC2/](BuildCorp-EC2/)
- **Guía de instalación, despliegue y defensa:** [README del proyecto](BuildCorp-EC2/README.md)
- **Registro de apoyo de IA:** [prompts_ia.md](BuildCorp-EC2/prompts_ia.md)

La aplicación usa Django, Django REST Framework y PostgreSQL. Nginx recibe las solicitudes públicas y las reenvía a Gunicorn. PostgreSQL y Gunicorn escuchan en localhost dentro de la misma EC2.

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
