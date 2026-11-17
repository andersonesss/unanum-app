# utils/constants.py
"""
Единый источник данных о знаках зодиака для всего проекта.

Использование:
    from utils.constants import (
        ZODIAC_SIGNS,          # полный список (12 знаков)
        ZODIAC_BY_KEY,         # 'aries' -> dict знака
        ZODIAC_RU_TO_KEY,      # 'Овен' -> 'aries'
        ZODIAC_NAMES_RU,       # ['Овен', 'Телец', ...] в порядке от Овна
        ELEMENT_MAP,           # 'Овен' -> 'Огонь'
        QUALITY_MAP,           # 'Овен' -> 'Кардинальный'
        get_zodiac_by_date,    # функция: 'YYYY-MM-DD' -> dict знака
    )
"""

# Порядок — как в натальной карте: Овен → Рыбы.
# start_month/start_day и end_month/end_day описывают диапазон.
# Для Козерога диапазон переходит через год: (12, 22) -> (1, 19).
# Условие проверки единое: (month == start_month and day >= start_day) or (month == end_month and day <= end_day).
ZODIAC_SIGNS = [
    {"key": "aries",       "name": "Овен",      "emoji": "♈", "element": "Огонь",   "quality": "Кардинальный",
     "dates": "21.03 – 19.04", "start_month": 3,  "start_day": 21, "end_month": 4,  "end_day": 19},
    {"key": "taurus",      "name": "Телец",     "emoji": "♉", "element": "Земля",   "quality": "Фиксированный",
     "dates": "20.04 – 20.05", "start_month": 4,  "start_day": 20, "end_month": 5,  "end_day": 20},
    {"key": "gemini",      "name": "Близнецы",  "emoji": "♊", "element": "Воздух",  "quality": "Мутабельный",
     "dates": "21.05 – 20.06", "start_month": 5,  "start_day": 21, "end_month": 6,  "end_day": 20},
    {"key": "cancer",      "name": "Рак",       "emoji": "♋", "element": "Вода",    "quality": "Кардинальный",
     "dates": "21.06 – 22.07", "start_month": 6,  "start_day": 21, "end_month": 7,  "end_day": 22},
    {"key": "leo",         "name": "Лев",       "emoji": "♌", "element": "Огонь",   "quality": "Фиксированный",
     "dates": "23.07 – 22.08", "start_month": 7,  "start_day": 23, "end_month": 8,  "end_day": 22},
    {"key": "virgo",       "name": "Дева",      "emoji": "♍", "element": "Земля",   "quality": "Мутабельный",
     "dates": "23.08 – 22.09", "start_month": 8,  "start_day": 23, "end_month": 9,  "end_day": 22},
    {"key": "libra",       "name": "Весы",      "emoji": "♎", "element": "Воздух",  "quality": "Кардинальный",
     "dates": "23.09 – 22.10", "start_month": 9,  "start_day": 23, "end_month": 10, "end_day": 22},
    {"key": "scorpio",     "name": "Скорпион",  "emoji": "♏", "element": "Вода",    "quality": "Фиксированный",
     "dates": "23.10 – 21.11", "start_month": 10, "start_day": 23, "end_month": 11, "end_day": 21},
    {"key": "sagittarius", "name": "Стрелец",   "emoji": "♐", "element": "Огонь",   "quality": "Мутабельный",
     "dates": "22.11 – 21.12", "start_month": 11, "start_day": 22, "end_month": 12, "end_day": 21},
    {"key": "capricorn",   "name": "Козерог",   "emoji": "♑", "element": "Земля",   "quality": "Кардинальный",
     "dates": "22.12 – 19.01", "start_month": 12, "start_day": 22, "end_month": 1,  "end_day": 19},
    {"key": "aquarius",    "name": "Водолей",   "emoji": "♒", "element": "Воздух",  "quality": "Фиксированный",
     "dates": "20.01 – 18.02", "start_month": 1,  "start_day": 20, "end_month": 2,  "end_day": 18},
    {"key": "pisces",      "name": "Рыбы",      "emoji": "♓", "element": "Вода",    "quality": "Мутабельный",
     "dates": "19.02 – 20.03", "start_month": 2,  "start_day": 19, "end_month": 3,  "end_day": 20},
]

# Быстрый доступ по ключу (англ. название)
ZODIAC_BY_KEY = {s["key"]: s for s in ZODIAC_SIGNS}

# Обратный маппинг: русское имя -> key
ZODIAC_RU_TO_KEY = {s["name"]: s["key"] for s in ZODIAC_SIGNS}

# Список русских имён в порядке от Овна к Рыбам
ZODIAC_NAMES_RU = [s["name"] for s in ZODIAC_SIGNS]

# Стихия и качество (для натальной карты)
ELEMENT_MAP = {s["name"]: s["element"] for s in ZODIAC_SIGNS}
QUALITY_MAP = {s["name"]: s["quality"] for s in ZODIAC_SIGNS}


def get_zodiac_by_date(birth_date):
    """Возвращает dict знака зодиака по дате 'YYYY-MM-DD' или None при ошибке.

    Единая функция для всего проекта — не дублировать логику диапазонов.
    """
    from datetime import datetime
    if not birth_date:
        return None
    try:
        dt = datetime.strptime(birth_date, '%Y-%m-%d')
    except (ValueError, TypeError):
        return None
    for s in ZODIAC_SIGNS:
        sm, sd = s["start_month"], s["start_day"]
        em, ed = s["end_month"], s["end_day"]
        if (dt.month == sm and dt.day >= sd) or (dt.month == em and dt.day <= ed):
            return s
    return None