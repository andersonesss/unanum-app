# Слушаем только loopback: снаружи Flask доступен ТОЛЬКО через Nginx
# (443/TLS → 127.0.0.1:8000). Иначе порт 8000 открыт из интернета напрямую:
# обход TLS, обход Nginx-level лимитов, plaintext-трафик к /api/admin/*,
# возможность IP-спуфинга через поддельный X-Forwarded-For (ProxyFix).
bind = "127.0.0.1:8000"
# Абсолютный путь к проекту: относительные пути (logs/, data/tarot_cards.json,
# instance/numer.db) зависят от CWD, gunicorn должен стартовать из корня проекта.
chdir = "/app"
# ВАЖНО: workers=1 обязателен, пока Flask-Limiter использует storage_uri="memory://".
# При нескольких воркерах счётчики лимитов не разделяются → лимиты в N раз выше.
# Для workers>1 перейти на Redis: LIMITER_STORAGE=redis://localhost:6379
workers = 1
worker_class = "gevent"
timeout = 360
graceful_timeout = 30
keepalive = 5
errorlog = "logs/gunicorn_error.log"
accesslog = "logs/gunicorn_access.log"
loglevel = "info"