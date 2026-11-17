# utils/helpers.py
import uuid
import time
from datetime import datetime
from flask import request, after_this_request, g
from flask_login import current_user

try:
    import pytz
    _MSK = pytz.timezone('Europe/Moscow')
except ImportError:
    _MSK = None


# In-memory кэш для get_location_by_ip: IP → (lat, lng, expires_at).
# TTL — 24 часа. Совместим с workers=1 (единственный воркер в gunicorn_config.py).
# Для workers>1 (Redis Limiter) понадобится внешний кэш.
_LOCATION_CACHE = {}
_LOCATION_CACHE_TTL = 24 * 3600


def now_msk() -> datetime:
    """Возвращает текущее время в Moscow timezone (UTC+3, без DST с 2014).

    Использовать вместо datetime.now(), чтобы 'сегодня' не сдвигалось
    на 1 день при работе сервера в UTC.
    """
    if _MSK is not None:
        return datetime.now(_MSK)
    return datetime.now()


def today_msk() -> str:
    """Возвращает текущую дату в Moscow timezone как 'YYYY-MM-DD'."""
    return now_msk().strftime('%Y-%m-%d')

def get_identifier():
    if current_user.is_authenticated:
        return current_user.email
    # В рамках одного запроса guest_id должен быть стабильным.
    # Без этого кэша при первом обращении гостя функция генерирует UUID
    # при каждом вызове (cookie ещё не установлена, request.cookies вернёт None),
    # что приводит к двум Set-Cookie в ответе и разным идентификаторам
    # для проверки лимита и для сохранения диалога.
    cached = getattr(g, '_guest_identifier', None)
    if cached:
        return cached
    guest_id = request.cookies.get('guest_id')
    if not guest_id:
        guest_id = str(uuid.uuid4())
        @after_this_request
        def set_cookie(response):
            response.set_cookie(
                'guest_id', guest_id,
                max_age=60*60*24*365,
                httponly=True,
                samesite='Lax'
            )
            return response
    result = f"guest:{guest_id}"
    g._guest_identifier = result
    return result


def get_location_by_ip(ip):
    try:
        import requests
        if ip in ('127.0.0.1', 'localhost', '::1') or ip.startswith('192.168.'):
            return 55.7558, 37.6173
        # Кэш: IP → (lat, lng, expires_at). TTL 24 часа.
        # Один и тот же IP при повторных заходах не ходит в сеть.
        cached = _LOCATION_CACHE.get(ip)
        if cached:
            lat_cached, lng_cached, expires_at = cached
            if expires_at > time.time():
                return lat_cached, lng_cached
        response = requests.get(f'https://ipapi.co/{ip}/json/', timeout=3)
        data = response.json()
        lat = data.get('latitude')
        lng = data.get('longitude')
        # Кэшируем только валидный ответ (оба числа). Ошибки не кэшируем —
        # следующий запрос попробует снова.
        if lat is not None and lng is not None:
            _LOCATION_CACHE[ip] = (lat, lng, time.time() + _LOCATION_CACHE_TTL)
        return lat, lng
    except:
        return 55.7558, 37.6173


def _migrate_guest_data(conn, guest_identifier, email):
    """Перенос данных гостя в аккаунт при логине."""
    # Перенос ответов опроса
    guest_insights = conn.execute(
        "SELECT * FROM daily_insights WHERE user_id = ?",
        (guest_identifier,)
    ).fetchall()
    for row in guest_insights:
        conn.execute(
            """INSERT OR REPLACE INTO daily_insights (user_id, insight_date, answers_json, tags_json)
            VALUES (?, ?, ?, ?)""",
            (email, row['insight_date'], row['answers_json'], row['tags_json'])
        )
    conn.execute("DELETE FROM daily_insights WHERE user_id = ?", (guest_identifier,))
    
    # Перенос истории карт дня
    guest_cards = conn.execute(
        "SELECT * FROM daily_cards WHERE identifier = ?",
        (guest_identifier,)
    ).fetchall()
    for row in guest_cards:
        conn.execute(
            """INSERT OR REPLACE INTO daily_cards (identifier, card_date, card_id, is_reversed, ai_text)
            VALUES (?, ?, ?, ?, ?)""",
            (email, row['card_date'], row['card_id'], row['is_reversed'], row['ai_text'])
        )
    conn.execute("DELETE FROM daily_cards WHERE identifier = ?", (guest_identifier,))
    
    # Перенос пробных раскладов
    conn.execute(
        "UPDATE spreads SET user_id = ? WHERE user_id = ?",
        (email, guest_identifier)
    )


def get_user_access_level():
    """Возвращает уровень доступа: 'plamya', 'brief' или 'guest'."""
    from flask_login import current_user
    if not current_user.is_authenticated:
        return 'brief'
    if current_user.subscription == 'Пламя':
        return 'plamya'
    # Для пользователей с тарифом Искра
    return 'brief'


def get_zodiac_sign(birth_date):
    """Определяет знак зодиака по дате рождения (YYYY-MM-DD).

    Делегирует логику в utils.constants.get_zodiac_by_date — единый источник
    диапазонов дат. Возвращает русское имя знака или None.
    """
    from utils.constants import get_zodiac_by_date
    sign = get_zodiac_by_date(birth_date)
    return sign["name"] if sign else None