import os

# В Docker gunicorn и nginx — разные контейнеры, поэтому слушаем 0.0.0.0.
# Наружу порт 8000 НЕ публикуется (в docker-compose у app нет ports),
# снаружи доступен только nginx (80/443) — loopback-ограничение здесь
# неприменимо, т.к. nginx ходит на app по bridge-сети.
bind = "0.0.0.0:8000"
# Абсолютный путь к проекту: относительные пути (logs/, data/tarot_cards.json,
# instance/numer.db) зависят от CWD, gunicorn должен стартовать из корня проекта.
chdir = "/app"
# Лимитер хранит счётчики в Redis (LIMITER_STORAGE=redis://redis:6379/0),
# поэтому несколько воркеров безопасно. WEB_CONCURRENCY задаёт docker-compose.
workers = int(os.getenv("WEB_CONCURRENCY", 2))
worker_class = "gevent"
timeout = 360
graceful_timeout = 30
keepalive = 5
errorlog = "logs/gunicorn_error.log"
accesslog = "logs/gunicorn_access.log"
loglevel = "info"