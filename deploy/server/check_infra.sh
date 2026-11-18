#!/bin/bash
cd /var/www/unanum
echo "=== tables ==="
docker compose exec -T db psql -U unanum -d unanum -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" 2>&1
echo "=== redis ==="
docker compose exec -T redis redis-cli ping 2>&1
echo "=== docker stats ==="
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}" 2>&1
echo "=== free ==="
free -h
echo "=== disk ==="
df -h / | tail -1
echo "=== app errors ==="
docker compose logs app 2>&1 | grep -iE "error|traceback" | grep -viE "pyswisseph|swisseph" | tail -20
