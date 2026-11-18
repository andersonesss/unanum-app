#!/bin/bash
cd /var/www/unanum
echo "=== userlist ==="
docker compose exec -T pgbouncer cat /etc/pgbouncer/userlist.txt 2>&1
echo "=== pgbouncer auth ==="
docker compose exec -T pgbouncer sh -c 'grep -E "auth_type|auth_file|user =" /etc/pgbouncer/pgbouncer.ini' 2>&1
echo "=== pg password_encryption ==="
docker compose exec -T db psql -U unanum -d unanum -Atc "SHOW password_encryption" 2>&1
echo "=== pg stored hash prefix ==="
docker compose exec -T db psql -U unanum -d unanum -Atc "SELECT left(rolpassword,14) FROM pg_authid WHERE rolname='unanum'" 2>&1
