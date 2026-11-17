FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# build-essential — сборка ephem / pyswisseph из исходников.
# libswe-dev НЕ ставим: Debian/Ubuntu не содержат Swiss Ephemeris,
# pyswisseph собирает SWE из собственных исходников.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN useradd -m -u 1000 app

WORKDIR /app
COPY . /app

RUN mkdir -p /app/logs /app/instance && chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/robots.txt || exit 1

CMD ["gunicorn", "-c", "gunicorn_config.py", "wsgi:app"]
