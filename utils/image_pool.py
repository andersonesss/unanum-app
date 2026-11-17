# utils/image_pool.py
"""ProcessPool для CPU-bound рендера картинок (Pillow).

На сервере 1 vCPU, поэтому max_workers=1: одновременно рендерится одна
картинка, остальные запросы получают 503 (nginx дополнительно ограничивает
/api/generate-card и /api/generate-share-card до 2r/m).

ВАЖНО (fork-safety): worker-процесс форкается от gunicorn-воркера и
наследует открытые соединения psycopg2 ThreadedConnectionPool. Использовать
их в двух процессах нельзя, поэтому в дочернем процессе ссылка на пул
обнуляется, а сам пул удерживается в _INHERITED_POOLS, чтобы его __del__
не отправил Terminate в PostgreSQL и не убил соединения родителя.
"""
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FuturesTimeout

from flask import abort

_INHERITED_POOLS = []


def _child_init():
    """Инициализатор worker-процесса: изолировать БД от родителя."""
    import database.db as db

    pool = getattr(db, "_pg_pool", None)
    if pool is not None:
        _INHERITED_POOLS.append(pool)
        db._pg_pool = None


_pool = ProcessPoolExecutor(max_workers=1, initializer=_child_init)


def run_image_job(fn, *args, timeout=60, **kwargs):
    """Выполнить рендер в отдельном процессе; при занятости — 503."""
    try:
        return _pool.submit(fn, *args, **kwargs).result(timeout=timeout)
    except FuturesTimeout:
        abort(503, description="Image generation busy, retry later")
