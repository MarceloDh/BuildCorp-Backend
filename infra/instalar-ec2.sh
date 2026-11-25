#!/usr/bin/env bash
set -euo pipefail

modo=$1
region=$2
bucket=$3
url=$4
export AWS_DEFAULT_REGION="$region"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
aws s3 cp "s3://$bucket/artefactos/buildcorp-eva4.tar.gz" "$tmp/buildcorp.tar.gz" --only-show-errors
tar -xzf "$tmp/buildcorp.tar.gz" -C "$tmp"
dnf install -y nginx

if [[ $modo == frontend ]]; then
  install -d -m 755 /var/www/buildcorp
  install -m 644 "$tmp/frontend"/{index.html,app.js,estilos.css} /var/www/buildcorp/
  printf 'window.BUILDCORP_API = new URL("/api/v4/", window.location.origin).href;\n' > /var/www/buildcorp/config.js
  cat >/etc/nginx/conf.d/buildcorp.conf <<'NGINX'
server {
    listen 80;
    server_name _;
    root /var/www/buildcorp;
    server_tokens off;
    add_header Content-Security-Policy "default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'self'" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Referrer-Policy no-referrer always;
    add_header Strict-Transport-Security "max-age=31536000" always;
    location = /salud-alb { try_files /index.html =503; }
    location / { try_files $uri $uri/ =404; }
}
NGINX
elif [[ $modo == backend ]]; then
  endpoint=$5
  secreto_db=$6
  parametro_demo=$7
  host=${url#https://}
  dnf install -y python3.11 python3.11-pip postgresql15 jq
  id buildcorp &>/dev/null || useradd --system --home-dir /opt/buildcorp --shell /sbin/nologin buildcorp
  install -d -m 755 /opt/buildcorp
  cp -R "$tmp/BuildCorp-EC2/." /opt/buildcorp/
  cd /opt/buildcorp
  curl --fail --silent --show-error --retry 3 "https://truststore.pki.rds.amazonaws.com/$region/$region-bundle.pem" -o rds-ca.pem
  chmod 644 rds-ca.pem
  python3.11 -m venv .venv
  .venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt

  master=$(aws secretsmanager get-secret-value --secret-id "$secreto_db" --query SecretString --output text)
  master_user=$(jq -er .username <<<"$master")
  master_password=$(jq -er .password <<<"$master")
  app_password=$(openssl rand -hex 32)
  if [[ -r .env ]]; then
    app_password=$(sed -n 's/^DB_PASSWORD=//p' .env)
  fi
  PGUSER="$master_user" PGPASSWORD="$master_password" PGHOST="$endpoint" PGDATABASE=buildcorp \
  PGSSLMODE=verify-full PGSSLROOTCERT="/opt/buildcorp/rds-ca.pem" APP_PASSWORD="$app_password" \
    psql -X --set ON_ERROR_STOP=1 <<'SQL'
\getenv clave APP_PASSWORD
SELECT format('CREATE ROLE buildcorp_app LOGIN PASSWORD %L', :'clave')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'buildcorp_app') \gexec
SELECT format('ALTER ROLE buildcorp_app PASSWORD %L', :'clave') \gexec
GRANT CONNECT ON DATABASE buildcorp TO buildcorp_app;
GRANT USAGE, CREATE ON SCHEMA public TO buildcorp_app;
SELECT ssl, version FROM pg_stat_ssl WHERE pid = pg_backend_pid();
SQL
  unset master master_password
  umask 027
  if [[ ! -f .env ]]; then
    cat >.env <<EOF
EVA4_AWS=1
DEBUG=0
HTTPS=1
HSTS_SECONDS=31536000
ALLOWED_HOSTS=$host,localhost
SECRET_KEY=$(openssl rand -hex 40)
JWT_SIGNING_KEY=$(openssl rand -hex 40)
DB_ENGINE=postgresql
DB_NAME=buildcorp
DB_USER=buildcorp_app
DB_PASSWORD=$app_password
DB_HOST=$endpoint
DB_PORT=5432
DB_SSLMODE=verify-full
DB_SSLROOTCERT=/opt/buildcorp/rds-ca.pem
RECURSOS_BUCKET=$bucket
RECURSOS_REGION=$region
EOF
    chown root:buildcorp .env
    chmod 640 .env
  fi
  runuser -u buildcorp -- .venv/bin/python manage.py migrate --noinput
  runuser -u buildcorp -- .venv/bin/python manage.py crear_roles
  demo_password=$(aws ssm get-parameter --name "$parametro_demo" --with-decryption --query Parameter.Value --output text)
  BUILDCORP_DEMO_PASSWORD="$demo_password" runuser -u buildcorp -- .venv/bin/python manage.py shell -c '
import os
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from inventario.access import SUPERVISOR, OPERADOR
for nombre, rol in (("supervision_demo", SUPERVISOR), ("bodega_demo", OPERADOR)):
    usuario, creado = get_user_model().objects.get_or_create(username=nombre)
    clave = os.environ["BUILDCORP_DEMO_PASSWORD"]
    validate_password(clave, usuario)
    usuario.set_password(clave)
    usuario.save()
    usuario.groups.add(Group.objects.get(name=rol))
print("Cuentas de demostración configuradas")
'
  unset demo_password app_password
  cat >/etc/systemd/system/buildcorp-eva4.service <<'SERVICE'
[Unit]
Description=BuildCorp API EVA4
After=network-online.target
Wants=network-online.target

[Service]
User=buildcorp
Group=buildcorp
WorkingDirectory=/opt/buildcorp
ExecStart=/opt/buildcorp/.venv/bin/gunicorn --workers 2 --bind 127.0.0.1:8000 buildcorp.wsgi:application
Restart=on-failure
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SERVICE
  cat >/etc/nginx/conf.d/buildcorp.conf <<NGINX
server {
    listen 80;
    server_name _;
    server_tokens off;
    client_max_body_size 64k;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header Authorization \$http_authorization;
    location = /salud-alb { proxy_pass http://127.0.0.1:8000/api/v4/salud/; }
    location /api/v4/ { proxy_pass http://127.0.0.1:8000; }
    location / { return 404; }
}
NGINX
  systemctl daemon-reload
  systemctl enable --now buildcorp-eva4
  systemctl restart buildcorp-eva4
else
  printf 'Modo inválido\n' >&2
  exit 2
fi

# El servidor por defecto de AL2023 también escucha en 80. Sustitúyelo por la
# configuración de BuildCorp y conserva los includes del paquete.
cat >/etc/nginx/nginx.conf <<'NGINX'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log;
pid /run/nginx.pid;
include /usr/share/nginx/modules/*.conf;
events { worker_connections 1024; }
http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    access_log /var/log/nginx/access.log;
    sendfile on;
    include /etc/nginx/conf.d/*.conf;
}
NGINX
nginx -t
systemctl enable --now nginx
systemctl restart nginx
for intento in {1..12}; do
  if curl --fail --silent -o /dev/null http://127.0.0.1/salud-alb; then
    printf '%s listo\n' "$modo"
    exit 0
  fi
  sleep 2
done
exit 1
