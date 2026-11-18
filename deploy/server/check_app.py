import os
import re
import sys
import time

import psycopg2
import requests

base = "http://127.0.0.1:8000"

# 1. PostgreSQL через pgbouncer
try:
    conn = psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=10,
    )
    cur = conn.cursor()
    cur.execute("SELECT 1")
    print("PG_OK", cur.fetchone()[0])
    conn.close()
except Exception as e:
    print("PG_FAIL", type(e).__name__, e)

# 2. Admin login (CSRF из формы /admin)
s = requests.Session()
r = s.get(base + "/admin", timeout=10)
m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
if not m:
    print("NO_CSRF", r.status_code)
    sys.exit(1)
token = m.group(1)
r2 = s.post(
    base + "/api/admin/login",
    json={"password": os.environ.get("ADMIN_MASTER_PASSWORD", "")},
    headers={"X-CSRFToken": token},
    timeout=10,
)
print("ADMIN_LOGIN", r2.status_code, "setcookie", bool(r2.headers.get("Set-Cookie")))

# 3. Генерация картинки (минимальная)
t = time.time()
r3 = s.post(
    base + "/api/generate-card",
    json={
        "type": "test",
        "title": "Test",
        "subtitle": "1",
        "main_text": "hello",
        "footer": "unanum",
        "tariff": "Искра",
    },
    headers={"X-CSRFToken": token},
    timeout=90,
)
print("IMAGE_MIN", r3.status_code, r3.headers.get("Content-Type"), len(r3.content), "bytes", round(time.time() - t, 2), "s")

# 4. Генерация картинки (реалистичный текст, тариф Пламя)
long_text = ("Финансовый код 6412 открывает энергию реализации. " * 8)[:200]
t = time.time()
r4 = s.post(
    base + "/api/generate-card",
    json={
        "type": "financial-code",
        "title": "Твой финансовый код",
        "subtitle": "6412",
        "main_text": long_text,
        "footer": "unanum",
        "tariff": "Пламя",
    },
    headers={"X-CSRFToken": token},
    timeout=90,
)
print("IMAGE_FULL", r4.status_code, r4.headers.get("Content-Type"), len(r4.content), "bytes", round(time.time() - t, 2), "s")
