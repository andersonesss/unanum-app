# utils/extensions.py
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# storage_uri:
#   - "memory://" — только для workers=1 (по умолчанию)
#   - "redis://localhost:6379" — для нескольких воркеров (задать LIMITER_STORAGE в .env)
limiter = Limiter(
    get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.getenv("LIMITER_STORAGE", "memory://")
)