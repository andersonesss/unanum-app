# utils/extensions.py
import os

from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def _is_localhost():
    """Healthcheck Docker идёт с 127.0.0.1 — его нельзя лимитировать,
    иначе healthcheck упирается в default_limits (50 per hour) и app
    становится unhealthy. Индивидуальные @limiter.limit на эндпоинтах
    продолжают работать — они не относятся к default_limits."""
    return request.remote_addr in ('127.0.0.1', '::1', 'localhost')


# storage_uri:
#   - "memory://" — только для workers=1 (по умолчанию)
#   - "redis://localhost:6379" — для нескольких воркеров (задать LIMITER_STORAGE в .env)
limiter = Limiter(
    get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.getenv("LIMITER_STORAGE", "memory://"),
    default_limits_exempt_when=_is_localhost
)