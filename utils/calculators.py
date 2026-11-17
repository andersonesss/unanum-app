# utils/calculators.py
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import ephem
import os
import logging
import random as _random

from utils.ai_service import (
    ai_natal_chart,
    ai_compatibility,
    ai_numerology_full,
    ask_deepseek
)

# ============================================
# ФИНАНСОВЫЙ КОД
# ============================================

def _build_financial_code_basics(birth_date, user_id=None):
    """
    Детерминированная часть финансового кода: валидация даты, расчёт
    4 цифр, базовый dict, portrait_hash и life_path.

    Не делает AI-вызовов. Возвращает dict:
        {
            'success': True,
            'code': str,                    # '6412'
            'digits_breakdown': list[dict], # 4 элемента
            'basic_result': dict,           # {'code': ...} + ['life_path']
            'portrait_hash': str | None,
            '_portrait_cache': dict | None,
            'dt': datetime,                 # пригодится в calculate_*
        }
    или {'error': str} при ошибке валидации.

    Используется в:
    - calculate_financial_code (классический JSON-ответ)
    - calculate_financial_code_stream (SSE)
    """
    from utils.helpers import now_msk

    try:
        dt = datetime.strptime(birth_date, '%Y-%m-%d')
    except (ValueError, TypeError):
        return {"error": "Неверный формат даты"}
    if dt > now_msk().replace(tzinfo=None):
        return {"error": "Дата рождения не может быть в будущем"}

    day = dt.day
    month = dt.month
    year = dt.year

    # Хэш портрета считаем один раз на весь вызов. Иначе ThreadPoolExecutor
    # (до 12 параллельных ask_deepseek) откроет по БД-сессии на каждую задачу
    # для получения портрета из _get_cache_key. Одна сессия вместо 12.
    portrait_hash = None
    _portrait_cache = None
    if user_id:
        try:
            from utils.orchestrator import get_or_create_portrait
            from utils.ai_service import compute_portrait_hash
            _portrait_cache = get_or_create_portrait(user_id)
            portrait_hash = compute_portrait_hash(_portrait_cache)
        except Exception:
            pass

    def reduce_to_single(n):
        while n > 9 and n not in [11, 22, 33]:
            n = sum(int(d) for d in str(n))
        return n

    def to_single(n):
        while n > 9:
            n = sum(int(d) for d in str(n))
        return n

    first_digit = to_single(day)
    second_digit = to_single(month)
    third_digit = to_single(year)

    all_digits = birth_date.replace('-', '')
    total_sum = sum(int(d) for d in all_digits)
    fourth_digit = to_single(total_sum)

    code = f"{first_digit}{second_digit}{third_digit}{fourth_digit}"

    digit_meanings = {
        0: "Ноль — чистая энергия возможностей. Всё только начинается, и ты можешь создать что угодно",
        1: "Единица (Лидер) — зарабатываешь самостоятельно, нужны новые проекты и риск. Деньги текут через твою инициативу",
        2: "Двойка (Партнёр) — деньги идут через команду, переговоры и дипломатию. Нужен надёжный партнёр",
        3: "Тройка (Оптимист) — деньги приходят через таланты, общение и творчество. Удача в рекламе и блогинге",
        4: "Четвёрка (Труженик) — стабильность и дисциплина. Заработок через упорный труд, порядок и семью",
        5: "Пятёрка (Путешественник) — деньги там, где риск и новые места (командировки, торговля). Избегай рутины",
        6: "Шестёрка (Семьянин) — финансы через заботу, образование, недвижимость. Нужно делиться, чтобы получить",
        7: "Семёрка (Аналитик) — самый сложный код. Деньги идут через интеллект (наука, IT), но требуют пауз и одиночества",
        8: "Восьмёрка (Управитель) — лучший код для бизнеса. Даёт большие деньги, власть и крупные проекты. Важно помогать другим",
        9: "Девятка (Благотворитель) — деньги как ресурс для помощи. Зарабатывай на высоких идеях (искусство, экология, психология)",
    }

    digits_breakdown = []
    digits = [first_digit, second_digit, third_digit, fourth_digit]
    position_names = [
        "Первая цифра (день)",
        "Вторая цифра (месяц)",
        "Третья цифра (год)",
        "Четвёртая цифра (сумма)"
    ]

    for i, digit in enumerate(digits):
        entry = {
            "position": position_names[i],
            "digit": digit,
            "meaning": digit_meanings.get(digit, "уникальная энергия")
        }
        digits_breakdown.append(entry)

    basic_result = {"code": code}

    # life_path — только для авторизованного (как было в оригинале)
    if user_id and _portrait_cache is not None:
        try:
            portrait = _portrait_cache
            if portrait.get('birth_date'):
                birth = portrait['birth_date']
                digits_sum = sum(int(d) for d in birth.replace('-', ''))
                life_path = reduce_to_single(digits_sum)
                while life_path > 9 and life_path not in [11, 22, 33]:
                    life_path = sum(int(d) for d in str(life_path))
                basic_result["life_path"] = life_path
        except Exception:
            pass

    return {
        'success': True,
        'code': code,
        'digits_breakdown': digits_breakdown,
        'basic_result': basic_result,
        'portrait_hash': portrait_hash,
        '_portrait_cache': _portrait_cache,
        'dt': dt,
        'reduce_to_single': reduce_to_single,
        'to_single': to_single,
    }

def _build_financial_code_tasks(mode, code, digits_breakdown, birth_date, user_id,
                                _portrait_cache, portrait_hash, detailed, dt,
                                reduce_to_single, to_single, basic_result):
    """
    Собирает AI-задачи для финансового кода.

    mode='classic' — набор задач как в calculate_financial_code
                     (без параллельных тизеров цифр).
    mode='stream'  — плюс 4 короткие teaser-задачи для цифр, которые
                     запускаются параллельно с полными. Дают «первые быстрые
                     буквы» для SSE-стрима.

    Возвращает:
        {
            'tasks': {key: {'sys': str, 'usr': str, 'temp': float, 'kind': str}, ...},
            'basic_result_fields': {...},  # поля, которые нужно смержить в basic_result
        }

    Изменения в basic_result НЕ производятся напрямую — всё возвращается
    через basic_result_fields, чтобы вызывающий мог явно их применить.

    kind (используется на стороне stream):
        'full'      — полный разбор цифры
        'teaser'    — короткий тизер цифры (только в mode='stream')
        'summary'   — общий вывод
        'life_path' — связка с числом жизненного пути
        'premium'   — премиум-секция (только для Пламени)
        'forecast'  — прогноз на год (только для Пламени)
    """
    tasks = {}
    basic_result_fields = {}

    # --- 4 полных разбора цифр ---
    for i, item in enumerate(digits_breakdown):
        sys_p = get_prompt_from_db('financial_code_digit')
        if not sys_p:
            sys_p = """Ты — нумеролог с многолетним опытом. Твой тон — как у мудрой наставницы: глубокий, тёплый, вдохновляющий.

    Разбери цифру финансового кода.

    Формат ответа — строго:
    Суть цифры в финансах (2-3 предложения)
    Как эта энергия проявляется в жизни: конкретный пример (2-3 предложения)
    Совет: как использовать эту цифру для увеличения дохода (1-2 предложения)

    Пиши сплошным текстом, без маркеров, без нумерации, без заголовков. Каждый блок начинай с новой строки.

    Правила:
    - Без обращения «ты», «твой», «вы», «ваш». Пиши безлично.
    - Без эмодзи, звёздочек, markdown.
    - Говори простым, человеческим языком.
    - Не используй шаблонные фразы: «звёзды шепчут», «деньги любят».
    - Длина: столько, сколько нужно для полного раскрытия темы."""
        usr_p = f"Цифра: {item['digit']}\nПозиция: {item['position']}\nНазвание из скобок: {item['meaning'][:50]}"
        if _portrait_cache is not None:
            themes = _portrait_cache.get('life_themes', [])
        else:
            themes = []
        if themes:
            usr_p += f"\nТемы, которые волнуют: {', '.join(themes)}. Мягко учти это, но не зацикливайся."
        usr_p += "\nРазбери эту цифру."
        tasks[f"digit_{i}"] = {'sys': sys_p, 'usr': usr_p, 'temp': 0.7, 'kind': 'full'}

    # --- summary ---
    tasks["summary"] = {
        'sys': """Ты — нумеролог. Напиши ОБЩИЙ ВЫВОД о финансовом коде.

    Развёрнутый вывод (3-4 предложения): как цифры кода работают вместе, какая главная сильная сторона, какая главная слабость, итоговая рекомендация.

    Правила:
    - Без обращения «ты», «твой», «вы».
    - Без эмодзи, звёздочек.
    - Последнее предложение должно начинаться с «Итоговая рекомендация:».""",
        'usr': f"Финансовый код: {code}\n" + "\n".join([f"Цифра {d['digit']} ({d['position']}): {d['meaning']}" for d in digits_breakdown]) + "\nНапиши общий вывод.",
        'temp': 0.7,
        'kind': 'summary',
    }

    # --- detailed (premium) ---
    tasks["detailed"] = {
        'sys': """Ты — нумеролог с 20-летним опытом. Твой тон — как у мудрой наставницы: простой, глубокий, без пафоса.

    СТРУКТУРА ОТВЕТА (строго соблюдай):
    1. Введение (1 предложение — общая характеристика кода)
    2. Разбор каждой цифры кода ОТДЕЛЬНО (для каждой цифры: номер, название в скобках, 3-4 предложения разбора)
    3. Как цифры взаимодействуют между собой (2-3 предложения)
    4. Итоговый совет (2-3 предложения — как использовать энергию кода максимально эффективно)

    ПРАВИЛА:
    - Без эмодзи, без обращений «ты», «твой».
    - Говори простым человеческим языком.
    - Выделяй цифры кода кавычками: например "четвёрка (4)".
    - Длина ответа: столько, сколько нужно для полного раскрытия темы. Не ограничивай себя.""",
        'usr': f"Финансовый код: {code}. Дата рождения: {birth_date}. Расскажи подробно о значении каждой цифры.",
        'temp': 0.7,
        'kind': 'premium',
    }

    # --- life_path_link ---
    # life_path уже посчитан в _build_financial_code_basics (если user_id и портрет).
    # Здесь используем его же и создаём задачу связки.
    life_path = basic_result.get("life_path")
    if life_path:
        tasks["life_path_link"] = {
            'sys': "Ты — нумеролог. Безлично, мягко, по делу.",
            'usr': f"Финансовый код человека: {code}. Число Жизненного Пути: {life_path}. Объясни в 2-3 предложениях, как эти числа взаимодействуют: усиливают ли они друг друга или создают вызов. Без обращений «ты», «вы». Безлично, тепло.",
            'temp': 0.7,
            'kind': 'life_path',
        }

    # --- premium-секции (только plamya + user_id) ---
    if detailed == 'plamya' and user_id:
        try:
            if life_path:
                tasks["personal_recs"] = {
                    'sys': "Ты — нумеролог. Безлично, коротко.",
                    'usr': f"Финкод: {code}. Жизненный путь: {life_path}. Дай 3 короткие персональные рекомендации по деньгам и карьере, учитывая оба числа. Каждая — 1 предложение. Каждую рекомендацию пиши с новой строки, без нумерации и маркеров. Без обращений. Без эмодзи.",
                    'temp': 0.7,
                    'kind': 'premium',
                }

                full_nums = {}
                full_nums['life_path'] = life_path
                full_nums['destiny'] = reduce_to_single(dt.day + dt.month + reduce_to_single(dt.year))
                full_nums['soul'] = reduce_to_single(dt.day)
                full_nums['maturity'] = reduce_to_single(life_path + full_nums['destiny'])

                tasks["oracle_full"] = {
                    'sys': "Ты — нумеролог. Глубокий анализ. Безлично, мудро.",
                    'usr': f"Финансовый код: {code}. Числа: Жизненный путь {full_nums['life_path']}, Судьба {full_nums['destiny']}, Душа {full_nums['soul']}, Зрелость {full_nums['maturity']}. Дай глубокий анализ: как эти числа вместе влияют на финансовый потенциал, какие сильные стороны и предостережения. 4-5 предложений. Без эмодзи, без обращений.",
                    'temp': 0.7,
                    'kind': 'premium',
                }

                from utils.helpers import now_msk
                current_year = now_msk().year
                forecast_years = []
                for offset in range(3):
                    year = current_year + offset
                    py_num = reduce_to_single(dt.day + dt.month + reduce_to_single(year))
                    tasks[f"forecast_{offset}"] = {
                        'sys': "Ты — нумеролог. Прогноз. Безлично, коротко.",
                        'usr': f"Год {year}, личное число года {py_num}. Финансовый код {code}. Опиши в 1-2 предложениях, какой финансовый результат принесёт этот год, учитывая энергию личного года и финкода. Без эмодзи, без обращений.",
                        'temp': 0.7,
                        'kind': 'forecast',
                    }
                    forecast_years.append((year, py_num))
                basic_result_fields["oracle_forecast_years"] = forecast_years

                # Ритуал — с учётом текущего лунного дня
                try:
                    moon = get_moon_phase_full(now_msk().strftime('%Y-%m-%d'), detailed=False)
                    lunar_day = moon.get('lunar_day', '?')
                    phase = moon.get('phase_name', '?')
                except Exception:
                    lunar_day, phase = '?', '?'
                tasks["ritual"] = {
                    'sys': "Ты — эзотерик-практик. Коротко, по делу.",
                    'usr': f"Финансовый код: {code}. Сегодня {lunar_day}-й лунный день, фаза {phase}. Придумай ОДИН развёрнутый персональный ритуал для привлечения денег, используя цифры кода и лунную энергию. Опиши конкретные действия, необходимые предметы, текст аффирмации. 5-7 предложений. Не используй эмодзи, звёздочки, кавычки-ёлочки и другое форматирование. Пиши обычным текстом, без обращений «ты», «вы».",
                    'temp': 0.8,
                    'kind': 'premium',
                }

                # Партнёр — если у пользователя есть сохранённый партнёр с датой рождения
                try:
                    from database.db import get_db
                    with get_db() as conn:
                        partner_row = conn.execute(
                            "SELECT * FROM partners WHERE user_id = ?",
                            (user_id,)
                        ).fetchone()
                    if partner_row and partner_row['birth_date']:
                        p_birth = partner_row['birth_date']
                        p_name = partner_row['name'] or 'Партнёр'
                        p_dt = datetime.strptime(p_birth, '%Y-%m-%d')
                        d1 = to_single(p_dt.day)
                        d2 = to_single(p_dt.month)
                        d3 = to_single(p_dt.year)
                        d4_raw = to_single(sum(int(d) for d in p_birth.replace('-', '')))
                        p_code = f"{d1}{d2}{d3}{d4_raw}"
                        basic_result_fields["oracle_partner_code"] = p_code
                        basic_result_fields["oracle_partner_name"] = p_name
                        tasks["partner"] = {
                            'sys': "Ты — нумеролог. Анализ совместимости. Безлично.",
                            'usr': f"Ваш финкод: {code}. Финкод партнёра ({p_name}): {p_code}. Проанализируйте совместимость финансовых энергий: как они взаимодействуют, где синергия, где конфликт. 3-4 предложения. Без эмодзи, без обращений.",
                            'temp': 0.7,
                            'kind': 'premium',
                        }
                except Exception:
                    pass
        except Exception:
            pass

    # --- stream-специфичные: короткие teaser-задачи по цифрам ---
    # Запускаются параллельно с полными. Дают «быстрые первые буквы» в SSE.
    if mode == 'stream':
        for i, item in enumerate(digits_breakdown):
            teaser_sys = (
                "Ты — нумеролог. Дай КОРОТКОЕ, интригующее описание цифры финансового кода — ровно 2-3 предложения.\n"
                "\n"
                "Структура:\n"
                "1. Название цифры и её главная суть в финансах (одно предложение, 5-10 слов).\n"
                "2. Интрига — вопрос, который бьёт в сердце (одно предложение, заканчивается знаком «?»).\n"
                "\n"
                "Правила:\n"
                "- Каждое предложение с новой строки.\n"
                "- Без обращения «ты», «твой», «вы».\n"
                "- Без эмодзи, звёздочек.\n"
                "- Последнее предложение — ВОПРОС со знаком «?»."
            )
            teaser_usr = (
                f"Цифра: {item['digit']}\n"
                f"Позиция: {item['position']}\n"
                f"Название: {item['meaning'][:50]}\n"
                f"Короткое интригующее описание цифры."
            )
            tasks[f"teaser_{i}"] = {
                'sys': teaser_sys,
                'usr': teaser_usr,
                'temp': 0.9,
                'kind': 'teaser',
            }

    return {'tasks': tasks, 'basic_result_fields': basic_result_fields}

def calculate_financial_code(birth_date, detailed=False, user_id=None):
    # Детерминированная часть — вынесена в _build_financial_code_basics.
    # Возвращает: code, digits_breakdown, basic_result (с life_path),
    # portrait_hash (для кэша AI), _portrait_cache, dt, хелперы.
    basics = _build_financial_code_basics(birth_date, user_id=user_id)
    if 'error' in basics:
        return {"error": basics['error']}

    code = basics['code']
    digits_breakdown = basics['digits_breakdown']
    basic_result = basics['basic_result']
    portrait_hash = basics['portrait_hash']
    _portrait_cache = basics['_portrait_cache']
    dt = basics['dt']
    reduce_to_single = basics['reduce_to_single']
    to_single = basics['to_single']

    if detailed == 'guest':
        return {"code": code, "upgrade_hint": True}

    # Сборка задач вынесена в _build_financial_code_tasks — один источник
    # промптов для classic-версии (эта функция) и stream-версии
    # (calculate_financial_code_stream). mode='classic' сохраняет прежний
    # набор задач: без параллельных тизеров, тизеры делаются ниже,
    # после получения полных текстов.
    tasks_bundle = _build_financial_code_tasks(
        mode='classic',
        code=code,
        digits_breakdown=digits_breakdown,
        birth_date=birth_date,
        user_id=user_id,
        _portrait_cache=_portrait_cache,
        portrait_hash=portrait_hash,
        detailed=detailed,
        dt=dt,
        reduce_to_single=reduce_to_single,
        to_single=to_single,
        basic_result=basic_result,
    )
    ai_tasks = tasks_bundle['tasks']
    basic_result.update(tasks_bundle['basic_result_fields'])

    results = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        future_to_key = {}
        for key, task in ai_tasks.items():
            future_to_key[executor.submit(
                ask_deepseek, task['sys'], task['usr'],
                temperature=task['temp'], user_id=user_id, portrait_hash=portrait_hash
            )] = key
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                results[key] = future.result(timeout=30)
            except Exception:
                results[key] = None

    for i, item in enumerate(digits_breakdown):
        ai_text = results.get(f"digit_{i}")
        if ai_text:
            item["meaning"] = ai_text
            teaser_prompt = """Ты — мастер коротких текстов. Ниже — ПОЛНЫЙ разбор цифры финансового кода. На его основе напиши ТРИ предложения.

        Структура:
        1. Первое предложение — номер цифры, название в скобках, главная суть (откуда приходят деньги). Бери ТОЛЬКО из полного ответа. 5-10 слов.
        2. Второе предложение — КОНКРЕТНЫЙ ПРИМЕР из полного ответа, который углубляет понимание. 5-10 слов.
        3. Третье предложение — ЭМОЦИОНАЛЬНАЯ ИНТРИГА. Вопрос, который бьёт в самое сердце. Ответ на него ДОЛЖЕН БЫТЬ в полном разборе. Используй приёмы: страх потери денег, надежда на прорыв, тайна упущенных возможностей.

        ПРИМЕР сильной интриги:
        «В какой момент эта цифра перестанет работать и начнёт разрушать финансовый поток?»
        «Сколько денег уже упущено из-за того, что энергия этой цифры используется неправильно?»

        Правила:
        - Каждое предложение с новой строки.
        - Бери факты ТОЛЬКО из полного ответа. Не выдумывай.
        - Без обращения «ты», «твой», «вы».
        - Без эмодзи, звёздочек.
        - Последнее предложение — ВОПРОС со знаком «?»."""
            
            item["teaser"] = ask_deepseek(teaser_prompt, f"Полный ответ:\n{ai_text}\n\nНапиши тизер из трёх предложений с сильной интригой. Факты бери ТОЛЬКО из полного ответа.", temperature=0.95, user_id=user_id, portrait_hash=portrait_hash)

    basic_result["digits_breakdown"] = digits_breakdown

    teaser_prompt_blocks = """Ты — мастер коротких текстов. Ниже — текст из полного разбора. Напиши ОДНО предложение (10-15 слов), которое создаст интригу и желание прочитать этот текст. Не пересказывай содержание. Не используй слова «в полном ответе», «в полной версии». Просто намекни на главную мысль или задай вопрос, на который отвечает этот текст.

    Пример:
    Текст: «Числа 1596 и 33 образуют глубокий союз. Энергия 33 несёт служение...»
    Тизер: «Два ключевых числа — финансовый код и жизненный путь — могут усиливать друг друга или создавать скрытый конфликт. Что происходит в этом случае?»
    """
    
    if results.get("life_path_link"):
        teaser_text = ask_deepseek(teaser_prompt_blocks, f"Текст:\n{results['life_path_link'][:500]}\n\nНапиши одно предложение-тизер:", temperature=0.85, user_id=user_id, portrait_hash=portrait_hash)
        if teaser_text:
            basic_result["life_path_link_teaser"] = teaser_text
    
    if detailed == 'plamya':
        for key, title in [
            ('detailed', 'Подробный анализ кода'),
            ('personal_recs', 'Персональные рекомендации'),
            ('oracle_full', 'Полный нумерологический разбор'),
        ]:
            if results.get(key):
                teaser_text = ask_deepseek(teaser_prompt_blocks, f"Текст:\n{results[key][:500]}\n\nНапиши одно предложение-тизер:", temperature=0.85, user_id=user_id, portrait_hash=portrait_hash)
                if teaser_text:
                    basic_result[f"{key}_teaser"] = teaser_text

    if results.get("summary"):
        basic_result["ai_summary"] = results["summary"]

    if detailed == 'plamya':
        if results.get("detailed"):
            basic_result["detailed_analysis"] = results["detailed"]

    if results.get("life_path_link"):
        basic_result["life_path_link"] = results["life_path_link"]

    if results.get("personal_recs"):
        rec_text = results["personal_recs"]
        import re
        recs = re.split(r'(?<=[.!?])\s+', rec_text)
        recs = [r.strip() for r in recs if r.strip()]
        if len(recs) < 3:
            recs = [r.strip() for r in rec_text.split('\n') if r.strip()]
        basic_result["personal_recommendations"] = recs[:3]

    if detailed == 'plamya':
        if results.get("oracle_full"):
            basic_result["oracle_full_analysis"] = results["oracle_full"]

        forecast_data = []
        for offset, (year, py_num) in enumerate(basic_result.get("oracle_forecast_years", [])):
            text = results.get(f"forecast_{offset}")
            if text:
                forecast_data.append({"year": year, "pn": py_num, "text": text.strip()})
        if forecast_data:
            basic_result["oracle_forecast"] = forecast_data

        if results.get("ritual"):
            basic_result["oracle_rituals"] = results["ritual"].strip()

        if results.get("partner"):
            basic_result["oracle_partner_analysis"] = results["partner"].strip()

    basic_result["recommendations"] = [
        "Что делать с кодом?",
        "Запиши свой финансовый код на бумаге и положи в кошелёк",
        "Повторяй его как аффирмацию каждое утро",
        "Используй цифры кода в паролях и пин-кодах (если это безопасно)",
        "Медитируй на свой код в полнолуние"
    ]

    return basic_result

def get_daily_financial_advice(code, digits_breakdown, user_id=None, detailed='brief'):
    """Генерирует ежедневный совет по денежному коду."""
    from utils.ai_service import ask_deepseek
    from utils.orchestrator import get_live_context
    
    # Получаем живой контекст
    live_context = {}
    if user_id:
        try:
            live_context = get_live_context(user_id)
        except:
            pass
    
    lunar_day = live_context.get('lunar_day', '?')
    phase_name = live_context.get('phase_name', '?')
    daily_card = live_context.get('daily_card', {}).get('name', '')
    
    # Формируем контекст для AI
    digits_info = "\n".join([f"Цифра {d['digit']} ({d['position']}): {d.get('meaning', d.get('teaser', ''))[:300]}" for d in digits_breakdown])
    
    system_prompt = f"""Ты - нумеролог. Дай ежедневный совет по денежному коду.

Лунный день: {lunar_day}, фаза: {phase_name}, карта дня: {daily_card}.

Структура ответа:
[SHORT] - два предложения. Первое: главная энергия дня для финансов. Второе: один конкретный совет по использованию денежного кода. Без интриги и вопросов - только суть. Закончи намёком на то, что в полном разборе есть продолжение.
[FULL] - развернутый совет (4-6 предложений): как энергия дня взаимодействует с цифрами денежного кода, какой конкретный шаг сделать для увеличения дохода, чего избегать в финансах, на какие сферы обратить внимание.

Правила:
- Без обращений "ты", "твой", "вы". Пиши безлично.
- Без эмодзи, звездочек.
- Привязывай совет к цифрам денежного кода и текущему лунному дню.
- [SHORT] и [FULL] должны быть на разных строках.
"""
    
    user_prompt = f"""Код: {code}
{digits_info}

Дай ежедневный совет на сегодня в формате [SHORT]...[FULL]..."""
    
    result = ask_deepseek(system_prompt, user_prompt, temperature=0.85, user_id=user_id)
    
    if not result:
        return None
    
    # re.search (не split) — как в get_daily_horoscope_advice.
    # split('[FULL]')[1] ломается, если AI продублирует '[FULL]' в тексте.
    import re as _re
    advice = {}
    short_match = _re.search(r'\[SHORT\](.*?)(\[FULL\]|$)', result, _re.DOTALL)
    full_match = _re.search(r'\[FULL\](.*?)(\[SHORT\]|$)', result, _re.DOTALL)

    if short_match and full_match:
        advice['short'] = short_match.group(1).strip()
        advice['full'] = full_match.group(1).strip()
    elif short_match:
        advice['short'] = short_match.group(1).strip()
        advice['full'] = result
    elif full_match:
        advice['short'] = result[:200] + '...'
        advice['full'] = full_match.group(1).strip()
    else:
        advice['short'] = result[:200] + '...'
        advice['full'] = result
    
    return advice

# ============================================
# ГОРОСКОП
# ============================================

def calculate_financial_code_stream(birth_date, detailed=False, user_id=None):
    """
    Генератор SSE-событий для финансового кода.

    Отдаёт кортежи (event_type, event_data):
        ('meta',  {code, digits_breakdown, planned_blocks, is_plamya})
        ('chunk', {chunk, name, phase})
        ('block', {name, value} или {name, value: None})
        ('done',  {code})
        ('error', {message})

    Стратегия (Подход B — стрим из буфера):
    1. Сначала 'meta' — код и 4 цифры (без AI-текстов).
    2. Параллельно запускаются:
       - 4 teaser-задачи (срочные, короткие, 2-3 предложения каждая),
       - все остальные (полные разборы цифр, summary, life_path,
         премиум-секции — только для Пламени).
    3. Teasers отдаются первыми — «быстрые первые буквы» в блок цифры.
       Каждый teaser стримится побуквенно (event:chunk с phase='teaser').
    4. Полные тексты — по мере готовности, тоже побуквенно
       (event:chunk с phase='full'), потом event:block.
    5. 'done' — когда все задачи отдали результат.

    mode='classic' в _build_financial_code_tasks НЕ используется.
    Используется mode='stream' — он добавляет teaser-задачи параллельно.
    """
    import queue
    import time
    from concurrent.futures import ThreadPoolExecutor
    from utils.ai_service import ask_deepseek

    # 1. Детерминированная часть (валидация, code, digits_breakdown,
    #    portrait_hash, life_path для авторизованных).
    basics = _build_financial_code_basics(birth_date, user_id=user_id)
    if 'error' in basics:
        yield ('error', {'message': basics['error']})
        return

    code = basics['code']
    digits_breakdown = basics['digits_breakdown']
    basic_result = basics['basic_result']
    portrait_hash = basics['portrait_hash']
    _portrait_cache = basics['_portrait_cache']
    dt = basics['dt']
    reduce_to_single = basics['reduce_to_single']
    to_single = basics['to_single']

    # 2. Guest — AI не нужен, отдаём код и завершаем.
    if detailed == 'guest':
        yield ('meta', {
            'code': code,
            'digits_breakdown': digits_breakdown,
            'upgrade_hint': True,
            'planned_blocks': [],
            'is_plamya': False,
        })
        yield ('done', {'code': code})
        return

    # 3. Мета: код + 4 цифры + список будущих блоков.
    #    planned_blocks — чтобы фронт мог сразу показать скелеты.
    planned_blocks = []
    for i in range(4):
        planned_blocks.append(f'teaser_{i}')
    for i in range(4):
        planned_blocks.append(f'digit_{i}')
    planned_blocks.extend(['summary', 'life_path_link'])
    if detailed == 'plamya':
        planned_blocks.extend([
            'detailed', 'personal_recs', 'oracle_full',
            'forecast_0', 'forecast_1', 'forecast_2',
            'ritual', 'partner',
        ])

    yield ('meta', {
        'code': code,
        'digits_breakdown': digits_breakdown,
        'planned_blocks': planned_blocks,
        'is_plamya': (detailed == 'plamya'),
    })

    # 4. Сборка задач (mode='stream' = teasers + полные цифры + summary +
    #    life_path_link + премиум для Пламени).
    tasks_bundle = _build_financial_code_tasks(
        mode='stream',
        code=code,
        digits_breakdown=digits_breakdown,
        birth_date=birth_date,
        user_id=user_id,
        _portrait_cache=_portrait_cache,
        portrait_hash=portrait_hash,
        detailed=detailed,
        dt=dt,
        reduce_to_single=reduce_to_single,
        to_single=to_single,
        basic_result=basic_result,
    )
    all_tasks = tasks_bundle['tasks']

    # 5. Разделяем на срочные (teasers) и остальные.
    teaser_keys = [k for k in all_tasks if k.startswith('teaser_')]
    full_keys = [k for k in all_tasks if not k.startswith('teaser_')]

    # 6. Хелперы.

    def _run_one(task, q, key):
        """Выполняет одну задачу в отдельном потоке и кладёт (key, text|None) в очередь."""
        try:
            text = ask_deepseek(
                task['sys'], task['usr'],
                temperature=task['temp'],
                user_id=user_id,
                portrait_hash=portrait_hash,
            )
            q.put((key, text))
        except Exception:
            q.put((key, None))

    def _stream_text(text, chunk_size=3, delay=0.006):
        """
        Нарезает текст на мелкие чанки для побуквенного эффекта.
        chunk_size — сколько символов в одном event:chunk.
        delay — пауза между чанками (сек). При gevent — кооперативная,
        при werkzeug dev — блокирующая (но это только локально).
        """
        for i in range(0, len(text), chunk_size):
            yield text[i:i + chunk_size]
            time.sleep(delay)

    # 7. Отдельные пулы: teasers (4 воркера) и остальные (6 воркеров).
    #    Разделение нужно, чтобы длинные задачи не занимали воркеры
    #    и не тормозили быстрые teasers.
    #
    #    ВАЖНО: выдаём результаты СТРОГО ПОСЛЕДОВАТЕЛЬНО — цифра 0, цифра 1,
    #    цифра 2, цифра 3. Внутри каждой: сначала teaser, потом full.
    #    Воркеры кладут результаты в очереди в порядке готовности, но
    #    главный поток выбирает нужный ключ (ждёт его, откладывая остальные
    #    в кэш-словари). Это даёт «как в DeepSeek»: один блок печатается
    #    до конца, потом следующий.
    teaser_q = queue.Queue()
    full_q = queue.Queue()

    ex_teaser = ThreadPoolExecutor(max_workers=4)
    ex_full = ThreadPoolExecutor(max_workers=6)

    # Кэш готовых результатов. Если нужный ключ ещё не пришёл из очереди —
    # тянем следующий результат, пока не встретим нужный. Отложенные
    # результаты лежат здесь и не теряются.
    teaser_cache = {}
    full_cache = {}

    def _wait_for_key(key, q, cache):
        """Достаёт результат конкретного ключа из кэша или ждёт из очереди.
        Остальные результаты, пришедшие раньше, складывает в кэш — их
        потом достанут следующие вызовы `_wait_for_key`."""
        if key in cache:
            return cache[key]
        while key not in cache:
            try:
                got_key, got_text = q.get(timeout=120)
            except queue.Empty:
                # DeepSeek не ответил за 120 сек — считаем, что упал.
                return None
            cache[got_key] = got_text
        return cache[key]

    try:
        for key in teaser_keys:
            ex_teaser.submit(_run_one, all_tasks[key], teaser_q, key)
        for key in full_keys:
            ex_full.submit(_run_one, all_tasks[key], full_q, key)

        # 8. Цифры — последовательно. Для каждой: teaser, потом full.
        for i in range(4):
            # --- teaser_i ---
            teaser_text = _wait_for_key(f'teaser_{i}', teaser_q, teaser_cache)
            if teaser_text:
                for chunk in _stream_text(teaser_text):
                    yield ('chunk', {
                        'chunk': chunk,
                        'name': f'digit_{i}',
                        'phase': 'teaser',
                    })
            yield ('block', {
                'name': f'teaser_{i}',
                'value': teaser_text,
            })

            # --- full_i (полный разбор цифры) ---
            full_text = _wait_for_key(f'digit_{i}', full_q, full_cache)
            if full_text:
                for chunk in _stream_text(full_text):
                    yield ('chunk', {
                        'chunk': chunk,
                        'name': f'digit_{i}',
                        'phase': 'full',
                    })
            yield ('block', {
                'name': f'digit_{i}',
                'value': full_text,
            })

        # 9. Остальные задачи (summary, life_path_link, премиум-секции) —
        #    в фиксированном читаемом порядке. `_wait_for_key` отложит
        #    всё, что придёт раньше, в кэш и вернёт нужный ключ, когда он
        #    придёт. Благодаря этому получаем предсказуемый порядок:
        #    сначала краткое summary, потом связь с жизненным путём,
        #    потом премиум-секции.
        #
        #    TODO (P5): для Искры задача 'detailed' сейчас создаётся
        #    в _build_financial_code_tasks всегда (без условия по тарифу),
        #    хотя фронт её не рендерит. Стоит убрать, чтобы не тратить
        #    токены DeepSeek. Вынести в отдельную задачу унификации.
        desired_order = [
            'summary',
            'life_path_link',
            'detailed',
            'personal_recs',
            'oracle_full',
            'forecast_0', 'forecast_1', 'forecast_2',
            'ritual',
            'partner',
        ]

        remaining_keys = []
        for k in desired_order:
            if k in all_tasks:
                remaining_keys.append(k)
        # Дописываем ключи, которых нет в desired_order (на будущее —
        # если раздел добавит новый блок, он не потеряется).
        for k in full_keys:
            if k.startswith('digit_'):
                continue
            if k not in remaining_keys:
                remaining_keys.append(k)

        for key in remaining_keys:
            text = _wait_for_key(key, full_q, full_cache)
            if text:
                for chunk in _stream_text(text, chunk_size=4, delay=0.004):
                    yield ('chunk', {
                        'chunk': chunk,
                        'name': key,
                        'phase': 'full',
                    })
            yield ('block', {'name': key, 'value': text})

    finally:
        # Гарантированно освобождаем потоки, даже если клиент оборвал
        # соединение и генератор получил GeneratorExit.
        ex_teaser.shutdown(wait=True)
        ex_full.shutdown(wait=True)

    # 10. Завершение.
    yield ('done', {'code': code})

def get_daily_horoscope(zodiac_sign, detailed=False, period="день", user_id=None):
    from utils.ai_service import (
        ai_horoscope_daily,
        ai_horoscope_love,
        ai_horoscope_career,
        ai_horoscope_health,
        ai_zodiac_description
    )
    from utils.constants import ZODIAC_BY_KEY

    # ZODIAC_BY_KEY[key] содержит: key, name, emoji, element, quality, dates, ...
    # Используем 'dates' вместо 'period' — тот же формат "21.03 – 19.04".
    sign_data = ZODIAC_BY_KEY.get(zodiac_sign.lower())
    if sign_data:
        sign = {
            "name": sign_data["name"],
            "emoji": sign_data["emoji"],
            "element": sign_data["element"],
            "period": sign_data["dates"],
        }
    else:
        sign = {"name": zodiac_sign, "emoji": "", "element": "", "period": ""}

    result = {
        "sign": sign["name"],
        "emoji": sign["emoji"],
        "element": sign["element"],
        "period": sign["period"],
        "period_type": period,
    }

    result["description"] = ai_zodiac_description(sign["name"], sign["element"], user_id=user_id) or ""
    # Полный прогноз
    full_daily = ai_horoscope_daily(sign["name"], sign["element"], user_id=user_id) or "Звёзды сегодня благосклонны."
    result["daily"] = full_daily

    # Генерируем тизер для daily
    teaser_prompt = """Ты — мастер коротких текстов. Ниже — полный гороскоп. Напиши ОДНО предложение (10-15 слов) с интригой. Дай ключевую информацию, но закончи вопросом или многоточием, не раскрывая главного совета.

    Правила:
    - Без обращений «ты», «твой», «вы».
    - Без эмодзи, звёздочек.
    - Не используй слова «в полном ответе», «в полной версии»."""
    result["daily_teaser"] = ask_deepseek(teaser_prompt, f"Полный гороскоп:\n{full_daily}\n\nНапиши одно предложение-тизер:", temperature=0.85, user_id=user_id) or full_daily[:100] + '...'

    # Генерируем полные тексты
    full_love = ai_horoscope_love(sign["name"], period, user_id=user_id) or "Гармония в отношениях."
    full_career = ai_horoscope_career(sign["name"], period, user_id=user_id) or "Благоприятное время для работы."
    full_health = ai_horoscope_health(sign["name"], period, user_id=user_id) or "Время позаботиться о себе."

    if detailed:
        # Платный тариф: отдаём полные тексты
        result["love"] = full_love
        result["career"] = full_career
        result["health"] = full_health
    else:
        # Бесплатный тариф: генерируем тизеры на основе полных текстов
        teaser_prompt = """Ты — мастер коротких текстов. Ниже — ПОЛНЫЙ астрологический прогноз. На его основе напиши ТРИ предложения (не больше 18 слов каждое).

Структура:
1. Первое предложение — главная энергия периода. Бери факты ТОЛЬКО из полного ответа ниже. Не выдумывай планеты, аспекты, транзиты — если их нет в тексте.
2. Второе предложение — ключевая рекомендация: один конкретный совет из полного ответа.
3. Третье предложение — интрига. Намекни на то, что раскрыто в полной версии, но не раскрывай сам совет.

ЖЁСТКИЕ ПРАВИЛА:
- Бери факты ТОЛЬКО из полного ответа ниже. Не придумывай планеты, знаки, аспекты.
- Без обращений «ты», «твой», «вы». Пиши безлично.
- Без эмодзи, звёздочек.
- Не используй слова «в полном ответе», «в полной версии».
- Каждое предложение с новой строки.
- Третье предложение ОБЯЗАНО заканчиваться знаком «?» или «...».
- Интрига должна звучать естественно, как продолжение мысли."""
        
        result["love_teaser"] = ask_deepseek(teaser_prompt, f"Полный прогноз:\n{full_love}\n\nНапиши тизер из трёх предложений:", temperature=0.85, user_id=user_id) or full_love[:150] + '...'
        result["career_teaser"] = ask_deepseek(teaser_prompt, f"Полный прогноз:\n{full_career}\n\nНапиши тизер из трёх предложений:", temperature=0.85, user_id=user_id) or full_career[:150] + '...'
        result["health_teaser"] = ask_deepseek(teaser_prompt, f"Полный прогноз:\n{full_health}\n\nНапиши тизер из трёх предложений:", temperature=0.85, user_id=user_id) or full_health[:150] + '...'

    return result


def get_daily_horoscope_stream(zodiac_sign, detailed=False, period="день", user_id=None):
    """

    Отдаёт кортежи (event_type, event_data), которые роут оборачивает
    через format_sse. Логика промптов и тизеров — идентична get_daily_horoscope,
    только запускается параллельно и отдаётся по мере готовности.

    События:
        ('meta', {sign, emoji, element, period, period_type, extra, planned_blocks})
        ('block', {name: 'description', value: '...'})
        ('block', {name: 'daily', value: '...', teaser: '...'})
        ('block', {name: 'love',   value: '...', teaser: '...'})  # teaser только для brief
        ('block', {name: 'career', value: '...', teaser: '...'})
        ('block', {name: 'health', value: '...', teaser: '...'})
        ('block', {name: 'daily_advice', short: '...', full: '...'})

    Параметр detailed:
        False (бесплатный) — блоки содержат full+teaser
        True  (платный)    — блоки содержат только full
    """
    from utils.stream_helpers import stream_block_tasks
    from utils.ai_service import (
        ai_horoscope_daily,
        ai_horoscope_love,
        ai_horoscope_career,
        ai_horoscope_health,
        ai_zodiac_description,
    )
    from utils.constants import ZODIAC_BY_KEY

    # --- Метаданные: отдаём сразу, до вызова AI ---
    sign_data = ZODIAC_BY_KEY.get(zodiac_sign.lower())
    if sign_data:
        sign = {
            "name": sign_data["name"],
            "emoji": sign_data["emoji"],
            "element": sign_data["element"],
            "period": sign_data["dates"],
        }
    else:
        sign = {"name": zodiac_sign, "emoji": "", "element": "", "period": ""}

    extra = ZODIAC_EXTRA.get(zodiac_sign.lower(), {})

    # Какие блоки придут — фронт может показать скелет «Загружается...»
    planned_blocks = ['description', 'daily', 'love', 'career', 'health', 'daily_advice']

    yield ('meta', {
        'sign': sign["name"],
        'emoji': sign["emoji"],
        'element': sign["element"],
        'period': sign["period"],
        'period_type': period,
        'extra': extra,
        'planned_blocks': planned_blocks,
    })

    # --- Промпты для тизеров (скопированы из get_daily_horoscope дословно) ---
    teaser_prompt_daily = """Ты — мастер коротких текстов. Ниже — полный гороскоп. Напиши ОДНО предложение (10-15 слов) с интригой. Дай ключевую информацию, но закончи вопросом или многоточием, не раскрывая главного совета.

    Правила:
    - Без обращений «ты», «твой», «вы».
    - Без эмодзи, звёздочек.
    - Не используй слова «в полном ответе», «в полной версии»."""

    teaser_prompt_3lines = """Ты — мастер коротких текстов. Ниже — ПОЛНЫЙ астрологический прогноз. На его основе напиши ТРИ предложения (не больше 18 слов каждое).

Структура:
1. Первое предложение — главная энергия периода. Бери факты ТОЛЬКО из полного ответа ниже. Не выдумывай планеты, аспекты, транзиты — если их нет в тексте.
2. Второе предложение — ключевая рекомендация: один конкретный совет из полного ответа.
3. Третье предложение — интрига. Намекни на то, что раскрыто в полной версии, но не раскрывай сам совет.

ЖЁСТКИЕ ПРАВИЛА:
- Бери факты ТОЛЬКО из полного ответа ниже. Не придумывай планеты, знаки, аспекты.
- Без обращений «ты», «твой», «вы». Пиши безлично.
- Без эмодзи, звёздочек.
- Не используй слова «в полном ответе», «в полной версии».
- Каждое предложение с новой строки.
- Третье предложение ОБЯЗАНО заканчиваться знаком «?» или «...».
- Интрига должна звучать естественно, как продолжение мысли."""

    # --- Обёртки задач. Каждая возвращает dict для event: block ---

    def _task_description():
        text = ai_zodiac_description(sign["name"], sign["element"], user_id=user_id) or ""
        return {'value': text}

    def _task_daily():
        text = ai_horoscope_daily(sign["name"], sign["element"], user_id=user_id) or "Звёзды сегодня благосклонны."
        teaser = ask_deepseek(
            teaser_prompt_daily,
            f"Полный гороскоп:\n{text}\n\nНапиши одно предложение-тизер:",
            temperature=0.85,
            user_id=user_id,
        ) or text[:100] + '...'
        return {'value': text, 'teaser': teaser}

    def _task_love():
        text = ai_horoscope_love(sign["name"], period, user_id=user_id) or "Гармония в отношениях."
        if detailed:
            return {'value': text}
        teaser = ask_deepseek(
            teaser_prompt_3lines,
            f"Полный прогноз:\n{text}\n\nНапиши тизер из трёх предложений:",
            temperature=0.85,
            user_id=user_id,
        ) or text[:150] + '...'
        return {'value': text, 'teaser': teaser}

    def _task_career():
        text = ai_horoscope_career(sign["name"], period, user_id=user_id) or "Благоприятное время для работы."
        if detailed:
            return {'value': text}
        teaser = ask_deepseek(
            teaser_prompt_3lines,
            f"Полный прогноз:\n{text}\n\nНапиши тизер из трёх предложений:",
            temperature=0.85,
            user_id=user_id,
        ) or text[:150] + '...'
        return {'value': text, 'teaser': teaser}

    def _task_health():
        text = ai_horoscope_health(sign["name"], period, user_id=user_id) or "Время позаботиться о себе."
        if detailed:
            return {'value': text}
        teaser = ask_deepseek(
            teaser_prompt_3lines,
            f"Полный прогноз:\n{text}\n\nНапиши тизер из трёх предложений:",
            temperature=0.85,
            user_id=user_id,
        ) or text[:150] + '...'
        return {'value': text, 'teaser': teaser}

    def _task_advice():
        advice = get_daily_horoscope_advice(
            zodiac_sign=sign["name"],
            period=period,
            user_id=user_id,
            detailed='plamya' if detailed else 'brief',
        )
        if advice:
            return {'short': advice.get('short', ''), 'full': advice.get('full', '')}
        return None

    tasks = [
        {'name': 'description', 'fn': _task_description},
        {'name': 'daily',       'fn': _task_daily},
        {'name': 'love',        'fn': _task_love},
        {'name': 'career',      'fn': _task_career},
        {'name': 'health',      'fn': _task_health},
        {'name': 'daily_advice','fn': _task_advice},
    ]

    # --- Параллельный запуск с отдачей блоков по готовности ---
    for name, result in stream_block_tasks(tasks, max_workers=6):
        if result is None:
            # Задача упала или вернула None — отдаём блок с value=None.
            # Фронт сам решит: пропустить или показать заглушку.
            yield ('block', {'name': name, 'value': None})
        else:
            yield ('block', {'name': name, **result})

def get_daily_horoscope_advice(zodiac_sign, period='день', user_id=None, detailed='brief'):
    """Генерирует ежедневный совет для гороскопа."""
    from utils.ai_service import ask_deepseek
    from utils.orchestrator import get_or_create_portrait, get_live_context
    
    live_context = {}
    if user_id:
        try:
            live_context = get_live_context(user_id)
        except:
            pass
    
    lunar_day = live_context.get('lunar_day', '?')
    phase_name = live_context.get('phase_name', '?')
    daily_card = live_context.get('daily_card', {}).get('name', '')
    time_of_day = live_context.get('time_of_day', 'день')
    
    from utils.constants import ZODIAC_BY_KEY
    sign_data = ZODIAC_BY_KEY.get(zodiac_sign.lower())
    sign_name = sign_data["name"] if sign_data else zodiac_sign
    
    period_text = period if period != 'день' else 'сегодня'
    system_prompt = f"""Ты - астролог. Составь гороскоп-совет для знака {sign_name} на {period_text}.

Лунный день: {lunar_day}, фаза: {phase_name}, карта дня: {daily_card}.

Структура ответа — строго два блока:

[FULL] — развернутый прогноз-совет (4-6 предложений):
- Как энергия периода взаимодействует со знаком.
- Какой конкретный шаг сделать.
- Чего избегать.
- На какие сферы обратить внимание.
- Одна неожиданная деталь, которая выделяет этот день среди других.

[SHORT] — два предложения, основанные СТРОГО на тексте из [FULL]:
- Первое предложение: возьми одну самую яркую фразу из [FULL] и перескажи её короче.
- Второе предложение: конкретный совет, взятый из [FULL], без интриги — только суть.
- Закончи намёком на то, что в полном разборе есть продолжение.

Правила:
- Без обращений "ты", "твой", "вы". Пиши безлично.
- Без эмодзи, звездочек.
- Привязывай совет к характеристикам знака и текущему лунному дню.
- [SHORT] должен содержать ТОЛЬКО факты из [FULL]. Не выдумывай новые темы.
- [FULL] и [SHORT] должны быть на разных строках, каждый начинается с соответствующего маркера."""
    
    user_prompt = f"Знак: {sign_name}\nПериод: {period_text}\nСначала напиши [FULL], затем [SHORT] на его основе."
    
    result = ask_deepseek(system_prompt, user_prompt, temperature=0.85, user_id=user_id)
    
    if not result:
        return None
    
    advice = {}
    import re
    short_match = re.search(r'\[SHORT\](.*?)(\[FULL\]|$)', result, re.DOTALL)
    full_match = re.search(r'\[FULL\](.*?)(\[SHORT\]|$)', result, re.DOTALL)
    
    if short_match and full_match:
        advice['short'] = short_match.group(1).strip()
        advice['full'] = full_match.group(1).strip()
    elif short_match:
        advice['short'] = short_match.group(1).strip()
        advice['full'] = result
    elif full_match:
        advice['short'] = result
        advice['full'] = full_match.group(1).strip()
    else:
        advice['short'] = result[:200] + '...'
        advice['full'] = result
    
    return advice

# ============================================
# ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ О ЗНАКАХ
# ============================================

ZODIAC_EXTRA = {
    'aries': {
        'color': 'Красный, золотой',
        'lucky_day': 'Пятница',
        'unlucky_day': 'Суббота',
        'stone': 'Рубин',
        'lucky_number': '3',
    },
    'taurus': {
        'color': 'Жёлтый, красный',
        'lucky_day': 'Среда',
        'unlucky_day': 'Вторник',
        'stone': 'Изумруд',
        'lucky_number': '5',
    },
    'gemini': {
        'color': 'Синий, розовый',
        'lucky_day': 'Четверг',
        'unlucky_day': 'Четверг',
        'stone': 'Агат',
        'lucky_number': '2',
    },
    'cancer': {
        'color': 'Зелёный, белый',
        'lucky_day': 'Суббота',
        'unlucky_day': 'Суббота',
        'stone': 'Лунный камень',
        'lucky_number': '1',
    },
    'leo': {
        'color': 'Оранжевый, жёлтый, красный',
        'lucky_day': 'Воскресенье',
        'unlucky_day': 'Среда',
        'stone': 'Бриллиант',
        'lucky_number': '1',
    },
    'virgo': {
        'color': 'Белый, розовый',
        'lucky_day': 'Среда',
        'unlucky_day': 'Пятница',
        'stone': 'Аметист',
        'lucky_number': '2',
    },
    'libra': {
        'color': 'Фиолетовый, жёлтый, розовый',
        'lucky_day': 'Воскресенье',
        'unlucky_day': 'Вторник',
        'stone': 'Опал',
        'lucky_number': '2',
    },
    'scorpio': {
        'color': 'Чёрный, фиолетовый, тёмно-фиолетовый',
        'lucky_day': 'Понедельник',
        'unlucky_day': 'Понедельник',
        'stone': 'Гранат',
        'lucky_number': '2',
    },
    'sagittarius': {
        'color': 'Жёлтый, красный, зелёный',
        'lucky_day': 'Среда',
        'unlucky_day': 'Среда',
        'stone': 'Голубой кристалл',
        'lucky_number': '0',
    },
    'capricorn': {
        'color': 'Серый, красный, фиолетовый',
        'lucky_day': 'Четверг',
        'unlucky_day': 'Понедельник',
        'stone': 'Сапфир',
        'lucky_number': '1',
    },
    'aquarius': {
        'color': 'Розовый, синий, сине-зелёный',
        'lucky_day': 'Понедельник',
        'unlucky_day': 'Воскресенье',
        'stone': 'Зелёный призрачный кристалл',
        'lucky_number': '1',
    },
    'pisces': {
        'color': 'Синий, зелёный',
        'lucky_day': 'Вторник',
        'unlucky_day': 'Среда',
        'stone': 'Хлорит (зелёный хрустальный камень)',
        'lucky_number': '1',
    },
}


# ============================================
# ПОЛНАЯ НУМЕРОЛОГИЯ (НОВАЯ)
# ============================================

def calculate_numerology_full(first_name, last_name, middle_name, birth_date, detailed='guest', user_id=None):
    import re

    result = {}
    full_name = f"{last_name or ''} {first_name or ''} {middle_name or ''}".strip()
    name_only = first_name or ''

    letter_map = {
        'а':1,'б':2,'в':3,'г':4,'д':5,'е':6,'ё':7,'ж':8,'з':9,
        'и':1,'й':2,'к':3,'л':4,'м':5,'н':6,'о':7,'п':8,'р':9,
        'с':1,'т':2,'у':3,'ф':4,'х':5,'ц':6,'ч':7,'ш':8,'щ':9,
        'ъ':1,'ы':2,'ь':3,'э':4,'ю':5,'я':6
    }
    vowels = set('аеёиоуыэюя')

    def letter_to_number(letter):
        return letter_map.get(letter.lower(), 0)

    def is_vowel(letter):
        return letter.lower() in vowels

    def reduce_number(n, keep_master=False):
        if keep_master and n in [11, 22, 33]:
            return n
        while n > 9:
            if keep_master and n in [11, 22, 33]:
                return n
            n = sum(int(d) for d in str(n))
        return n

    from utils.helpers import now_msk
    try:
        dt = datetime.strptime(birth_date, '%Y-%m-%d')
        if dt > now_msk().replace(tzinfo=None):
            return {"error": "Дата рождения не может быть в будущем"}
        day = dt.day
        month = dt.month
        year = dt.year
    except:
        return {"error": "Неверный формат даты"}

    birth_digits = [int(d) for d in birth_date.replace('-', '')]

    life_path_sum = sum(birth_digits)
    life_path = reduce_number(life_path_sum, keep_master=True)
    result["life_path"] = {
        "number": life_path,
        "title": get_life_path_title(life_path),
        "description": get_life_path_description(life_path)
    }

    soul_date = reduce_number(day, keep_master=True)
    result["soul_date"] = {
        "number": soul_date,
        "description": get_soul_date_description(soul_date)
    }

    if full_name:
        name_sum = sum(letter_to_number(c) for c in full_name if c.isalpha())
        destiny = reduce_number(name_sum, keep_master=True)

        result["destiny"] = {
            "number": destiny,
            "title": get_destiny_title(destiny),
            "description": get_destiny_description(destiny)
        }

        maturity = reduce_number(life_path + destiny)
        result["maturity"] = {
            "number": maturity,
            "description": get_maturity_description(maturity)
        }

        result["expression"] = {
            "number": destiny,
            "description": get_expression_description(destiny, name_only)
        }

        vowel_sum = sum(letter_to_number(c) for c in full_name if c.isalpha() and is_vowel(c))
        soul_name = reduce_number(vowel_sum, keep_master=True)
        result["soul_name"] = {
            "number": soul_name,
            "description": get_soul_name_description(soul_name)
        }

        consonant_sum = sum(letter_to_number(c) for c in full_name if c.isalpha() and not is_vowel(c))
        personality = reduce_number(consonant_sum, keep_master=True)
        result["personality"] = {
            "number": personality,
            "description": get_personality_description(personality)
        }

    karmic_numbers = [13, 14, 16, 19]
    has_karmic = life_path_sum in karmic_numbers or soul_date in karmic_numbers
    result["karmic_debt"] = {
        "has_debt": has_karmic,
        "number": life_path_sum if life_path_sum in karmic_numbers else (soul_date if soul_date in karmic_numbers else None),
        "description": get_karmic_description(life_path_sum) if has_karmic else "Кармический долг отсутствует. Ты пришла с чистым листом."
    }

    peak1 = reduce_number(month + day)
    peak2 = reduce_number(day + reduce_number(year))
    peak3 = reduce_number(peak1 + peak2)
    peak4 = reduce_number(month + reduce_number(year))

    peaks_data = [
        {"age": "0–28 лет", "number": peak1, "peak_num": 1},
        {"age": "28–37 лет", "number": peak2, "peak_num": 2},
        {"age": "37–46 лет", "number": peak3, "peak_num": 3},
        {"age": "46+ лет", "number": peak4, "peak_num": 4},
    ]

    result["peaks"] = []
    for p in peaks_data:
        desc = get_peak_description(p["number"], p["peak_num"])
        if detailed == 'plamya':
            ai_peak = ask_deepseek(
                system_prompt="""Ты - нумеролог. Опиши жизненный пик человека. 
    3-4 предложения: что ждёт в этот период, как пройти, что важно понять.
    Без эмодзи, без обращений "ты", "вы". Безлично, вдохновляюще.""",
                user_prompt=f"Пик {p['number']}, возраст {p['age']}. Имя: {name_only}. Дай описание.",
                temperature=0.7,
                user_id=user_id
            )
            if ai_peak:
                desc = ai_peak
        result["peaks"].append({
            "age": p["age"],
            "number": p["number"],
            "description": desc
        })

    current_year = now_msk().year
    personal_year = reduce_number(day + month + reduce_number(current_year))
    personal_year_desc = get_personal_year_description(personal_year)
    if detailed == 'plamya':
        ai_py = ask_deepseek(
            system_prompt="""Ты - нумеролог. Опиши личный год человека.
4-5 предложений: что принесёт этот год, на что обратить внимание, какие сферы будут важны.
Без эмодзи, без обращений "ты", "вы". Безлично, вдохновляюще.""",
            user_prompt=f"Год {current_year}, число года {personal_year}. Имя: {name_only}. Дай описание.",
            temperature=0.7,
            user_id=user_id
        )
        if ai_py:
            personal_year_desc = ai_py

    result["personal_year"] = {
        "year": current_year,
        "number": personal_year,
        "description": personal_year_desc
    }

    first_extra = life_path_sum
    second_extra = reduce_number(first_extra)
    first_digit = int(str(day).lstrip('0')[0]) if str(day).lstrip('0') else 0
    third_extra = first_extra - 2 * first_digit
    fourth_extra = reduce_number(third_extra) if third_extra > 9 else third_extra
    if fourth_extra == 0:
        fourth_extra = third_extra

    all_digits = birth_digits + \
                 [int(d) for d in str(first_extra)] + \
                 [int(d) for d in str(second_extra)] + \
                 [int(d) for d in str(third_extra)] + \
                 [int(d) for d in str(fourth_extra)]

    counts = {i: 0 for i in range(1, 10)}
    for d in all_digits:
        if d != 0:
            counts[d] = counts.get(d, 0) + 1

    pythagoras = {}
    for i in range(1, 10):
        count = counts[i]
        value_str = str(i) * count if count > 0 else "—"
        cell_name = get_cell_name(i)
        description = ""
        
        if detailed == 'plamya':
            cell_prompt = f"Ты — нумеролог. Опиши значение ячейки «{cell_name}» в квадрате Пифагора. Значение: {value_str} (количество цифр {count}). Дай развёрнутый ответ (8-10 предложений): что означает эта ячейка, как влияет на жизнь и характер, сильные стороны этого качества, возможные слабости или вызовы, совет: как развить или сбалансировать. Тон — мягкий, женственный, вдохновляющий. Без эмодзи, без обращений «ты», «вы». Безлично."
            
            ai_desc = ask_deepseek(
                system_prompt=cell_prompt,
                user_prompt=f"Ячейка: {cell_name}. Значение: {value_str}. Имя: {name_only}. Дай развёрнутое описание.",
                temperature=0.7,
                user_id=user_id
            )
            if ai_desc:
                description = ai_desc
        else:
            description = get_cell_description(i, count)
        
        pythagoras[f"cell{i}"] = {
            "number": i,
            "count": count,
            "value": value_str,
            "name": cell_name,
            "description": description
        }

    lines = {
        "purpose": f"Целеустремлённость: {counts[1]}{counts[4]}{counts[7]}",
        "family": f"Семья: {counts[2]}{counts[5]}{counts[8]}",
        "habits": f"Привычки: {counts[3]}{counts[6]}{counts[9]}",
        "spirit": f"Духовность: {counts[1]}{counts[5]}{counts[9]}",
        "body": f"Тело: {counts[3]}{counts[5]}{counts[7]}",
    }
    result["pythagoras"] = {"cells": pythagoras, "lines": lines}

    if detailed == 'plamya' and full_name:
        numbers_summary = {k: v.get('number', v) for k, v in result.items() if isinstance(v, dict) and 'number' in v}
        full_ai = ai_numerology_full(full_name, birth_date, numbers_summary, user_id=user_id)
        if full_ai:
            result["ai_full"] = full_ai

        weakness_keys = {'life_path', 'soul_date', 'soul_name'}
        challenge_keys = {'destiny', 'personality', 'expression', 'maturity'}

        for key in ['life_path', 'soul_date', 'maturity', 'expression', 'soul_name', 'personality']:
            if key in result and isinstance(result[key], dict):
                num = result[key].get('number')
                if num:
                    third_section = "Слабые стороны" if key in weakness_keys else "Вызовы и трудности"
                    
                    ai_text = ask_deepseek(
                        system_prompt=f"Ты — нумеролог. Опиши значение числа для человека. Ответ строго по структуре: Значение: (2-3 предложения о сути числа для имени {name_only}), Сильные стороны: (2-3 предложения о преимуществах), {third_section}: (2-3 предложения). Каждый раздел с новой строки. Без маркеров, без эмодзи, без обращений «ты», «вы». Безлично, женственно, мягко.",
                        user_prompt=f"Число: {num}. Имя: {name_only}. Дай описание.",
                        temperature=0.7,
                        user_id=user_id
                    )
                    if ai_text:
                        result[key]["ai_description"] = ai_text

    if detailed == 'guest':
        return {"error": "Войди, чтобы увидеть нумерологический портрет"}
    if detailed == 'brief':
        return {
            "life_path": result.get("life_path"),
            "destiny": result.get("destiny"),
            "upgrade_hint": True
        }
    if detailed == 'numbers_only':
        # Новый режим для SSE-стрима: возвращает все числа без AI-вызовов.
        # Порядок вызовов AI (peaks, personal_year, ai_full, ai_descriptions)
        # стоит ВЫШЕ этой проверки и НЕ выполняется, если detailed != 'plamya'.
        # То есть 'numbers_only' фактически обрабатывается как «AI не запускать».
        return result
    return result


def calculate_life_graph(birth_date):
    """Рассчитывает график жизни по дате рождения.
    Возвращает: code, cycles, current_period, current_level, current_start, current_end.
    """
    from utils.helpers import now_msk
    try:
        dt = datetime.strptime(birth_date, '%Y-%m-%d')
        if dt > now_msk().replace(tzinfo=None):
            return {"error": "Дата рождения не может быть в будущем"}
    except:
        return {"error": "Неверный формат даты"}
    
    day = dt.day
    month = dt.month
    year = dt.year
    
    product = day * month * year
    product_str = str(product)
    
    # Код графика — произведение без дополнения до 7 цифр
    graph_code = product_str
    
    cycles = [int(d) for d in graph_code]
    
    birth_year = year
    current_age = now_msk().year - birth_year
    current_period = current_age // 7
    if current_period >= len(cycles):
        current_period = len(cycles) - 1
    current_level = cycles[current_period]
    current_start = current_period * 7
    current_end = current_start + 6
    
    return {
        "code": graph_code,
        "cycles": cycles,
        "current_period": current_period,
        "current_level": current_level,
        "current_start": current_start,
        "current_end": current_end
    }


# ============================================
# БАЗА ТРАКТОВОК НУМЕРОЛОГИИ
# ============================================

def get_life_path_title(number):
    titles = {
        1: "Лидер", 2: "Миротворец", 3: "Творец",
        4: "Строитель", 5: "Искатель", 6: "Хранитель",
        7: "Мудрец", 8: "Управитель", 9: "Служитель",
        11: "Мастер-вдохновитель", 22: "Мастер-созидатель", 33: "Мастер-учитель"
    }
    return titles.get(number, "Уникальный путь")

def get_life_path_description(number):
    descriptions = {
        1: "Твоя миссия — прокладывать путь. Ты прирождённый лидер, новатор, первопроходец. Твоя сила — в умении начинать новое и вести за собой. Ошибка — одиночество из-за гордыни или нежелания слушать других.",
        2: "Твоя миссия — создавать гармонию. Ты дипломат, миротворец, тонко чувствующий человек. Твоя сила — в умении объединять людей. Ошибка — забывать о себе ради других.",
        3: "Твоя миссия — нести радость и красоту. Ты творческая натура с даром вдохновлять. Твоя сила — в самовыражении через слово, искусство, общение. Ошибка — распыляться на пустое.",
        4: "Твоя миссия — строить надёжный фундамент. Ты организована, дисциплинирована, верна своему делу. Твоя сила — в стабильности и упорстве. Ошибка — застревать в рутине и бояться перемен.",
        5: "Твоя миссия — познавать мир через опыт. Ты свободолюбива, энергична, обожаешь приключения. Твоя сила — в адаптивности и жажде нового. Ошибка — непостоянство и избегание обязательств.",
        6: "Твоя миссия — заботиться и создавать уют. Ты хранительница очага, наставница, душа компании. Твоя сила — в любви и ответственности. Ошибка — растворяться в других до потери себя.",
        7: "Твоя миссия — искать истину. Ты глубокий мыслитель, аналитик, интуит. Твоя сила — в мудрости и умении видеть суть. Ошибка — уходить в изоляцию и отстранённость.",
        8: "Твоя миссия — управлять ресурсами. Ты прирождённый организатор, финансист, лидер. Твоя сила — в умении достигать целей. Ошибка — ставить деньги выше людей.",
        9: "Твоя миссия — служить человечеству. Ты гуманист, идеалист, целитель душ. Твоя сила — в сострадании и мудрости. Ошибка — забывать о земных делах.",
        11: "Твоя миссия — нести свет и вдохновение. Ты обладаешь сильной интуицией и даром вести за собой духовно. Ошибка — сомневаться в своей силе.",
        22: "Твоя миссия — воплощать великие мечты в реальность. Ты способна создавать проекты мирового масштаба. Ошибка — бояться своего размаха.",
        33: "Твоя миссия — учить любви и служению. Ты мастер-учитель, несущий безусловную любовь. Ошибка — перфекционизм и выгорание."
    }
    return descriptions.get(number, "Твой путь уникален и прекрасен.")

def get_destiny_title(number):
    return get_life_path_title(number)

def get_destiny_description(number):
    descriptions = {
        1: "Число Судьбы 1 говорит о лидерских талантах. Твоё имя несёт энергию первопроходца. Ты способна начинать проекты и вести за собой. Карьера: руководитель, предприниматель.",
        2: "Число Судьбы 2 раскрывает дар дипломатии. Твоё имя мягко влияет на людей. Ты хороша в переговорах и командной работе. Карьера: психолог, консультант.",
        3: "Число Судьбы 3 — творческий потенциал. Твоё имя звучит как песня. Ты талантлива в искусстве, блогинге, публичных выступлениях. Карьера: артист, журналист.",
        4: "Число Судьбы 4 — организаторский талант. Твоё имя несёт стабильность. Ты умеешь систематизировать и доводить до конца. Карьера: инженер, архитектор.",
        5: "Число Судьбы 5 — энергия свободы. Твоё имя манит приключениями. Ты талантлива в продажах, путешествиях, коммуникациях. Карьера: маркетолог, тревел-блогер.",
        6: "Число Судьбы 6 — дар заботы. Твоё имя излучает тепло. Ты талантлива в обучении, медицине, дизайне. Карьера: педагог, врач, дизайнер интерьеров.",
        7: "Число Судьбы 7 — аналитический дар. Твоё имя хранит мудрость. Ты талантлива в науке, IT, исследованиях. Карьера: аналитик, программист.",
        8: "Число Судьбы 8 — дар управления. Твоё имя притягивает изобилие. Ты талантлива в бизнесе и финансах. Карьера: директор, финансист.",
        9: "Число Судьбы 9 — дар служения. Твоё имя несёт сострадание. Ты талантлива в психологии, экологии, благотворительности. Карьера: психолог, эколог.",
        11: "Число Судьбы 11 — дар вдохновения. Твоё имя вибрирует на высоких частотах. Ты способна вести людей духовно. Карьера: коуч, духовный учитель.",
        22: "Число Судьбы 22 — дар созидания. Твоё имя способно менять мир. Ты можешь создавать организации и проекты глобального масштаба.",
        33: "Число Судьбы 33 — дар безусловной любви. Твоё имя — благословение. Ты способна исцелять словом и присутствием."
    }
    return descriptions.get(number, "Твоё имя несёт уникальную энергию.")

def get_soul_date_description(number):
    descriptions = {
        1: "В глубине души ты жаждешь признания и самостоятельности. Тебе важно быть первой, даже если внешне ты мягка.",
        2: "Твоя душа ищет гармонию и партнёрство. Ты расцветаешь, когда есть надёжный человек рядом.",
        3: "Твоя душа поёт. Тебе жизненно необходимо творчество, общение и радость.",
        4: "Внутри ты жаждешь порядка и стабильности. Хаос выбивает тебя из колеи.",
        5: "Твоя душа — вольный ветер. Тебе нужны перемены, новые места и впечатления.",
        6: "Твоя душа хочет любить и быть любимой. Забота о близких — твой источник счастья.",
        7: "Твоя душа — исследователь. Тебе нужно время в тишине, чтобы понять себя.",
        8: "Твоя душа стремится к изобилию. Тебе важно чувствовать контроль над своей жизнью.",
        9: "Твоя душа — целитель. Ты чувствуешь чужую боль и хочешь помогать.",
        11: "Твоя душа — пророк. Тебе снятся вещие сны, ты чувствуешь тонкие энергии.",
        22: "Твоя душа — архитектор. Ты видишь картину целиком там, где другие видят хаос.",
        33: "Твоя душа — ангел. Ты пришла с миссией любви и прощения."
    }
    return descriptions.get(number, "Твоя душа знает путь.")

def get_maturity_description(number):
    descriptions = {
        1: "После 35 лет ты раскроешься как лидер. Время взять управление жизнью в свои руки.",
        2: "Зрелость принесёт тебе дар дипломатии. Ты станешь тем человеком, к кому идут за советом.",
        3: "После 35 ты расцветёшь творчески. Второе дыхание в искусстве или общении.",
        4: "Зрелость укрепит твой фундамент. Ты построишь то, что останется после тебя.",
        5: "После 35 — время свободы. Путешествия, смена профессии, новый виток.",
        6: "Зрелость раскроет твой дар наставницы. Ты будешь передавать опыт и заботиться.",
        7: "После 35 ты уйдёшь в глубину. Духовные практики, наука, самопознание.",
        8: "Зрелость принесёт финансовый расцвет. Твой управленческий талант раскроется полностью.",
        9: "После 35 ты обратишься к служению. Благотворительность, экология, помощь людям."
    }
    return descriptions.get(number, "Зрелость откроет новые грани твоей личности.")

def get_expression_description(number, name):
    return get_destiny_description(number)

def get_soul_name_description(number):
    descriptions = {
        1: "Эмоционально ты нуждаешься в признании. Тебе важно, чтобы твои усилия замечали.",
        2: "Твоё сердце жаждет гармонии. Конфликты истощают тебя больше, чем физическая работа.",
        3: "Эмоционально ты — ребёнок. Тебе нужна радость, игра и творческое выражение.",
        4: "Твоё сердце ищет стабильности. Без прочного тыла ты чувствуешь тревогу.",
        5: "Эмоционально ты нуждаешься в свободе. Ограничения душат твою душу.",
        6: "Твоё сердце наполняется, когда ты заботишься. Но помни: сначала — себе.",
        7: "Эмоционально ты самодостаточна. Тебе нужно личное пространство для восстановления.",
        8: "Твоё сердце хочет изобилия. Но не в деньгах — в ощущении «у меня всё под контролем».",
        9: "Эмоционально ты — эмпат. Ты впитываешь чувства других, учись ставить границы."
    }
    return descriptions.get(number, "Твоё сердце знает, что ему нужно.")

def get_personality_description(number):
    descriptions = {
        1: "Окружающие видят в тебе лидера. Ты кажешься уверенной и решительной, даже когда сомневаешься.",
        2: "Люди воспринимают тебя как мягкого и тактичного человека. Ты располагаешь к себе с первого взгляда.",
        3: "Ты производишь впечатление жизнерадостного и творческого человека. С тобой хочется дружить.",
        4: "Окружающие видят в тебе надёжного человека. Ты кажешься серьёзной и ответственной.",
        5: "Люди видят в тебе свободного духа. Ты притягиваешь своей энергией и жаждой приключений.",
        6: "Ты производишь впечатление заботливого и тёплого человека. К тебе идут за советом и утешением.",
        7: "Окружающие видят в тебе загадку. Ты кажешься глубокой и немного отстранённой.",
        8: "Люди воспринимают тебя как сильного и властного человека. Ты внушаешь уважение.",
        9: "Ты производишь впечатление мудрого и сострадательного человека. Ты светишься изнутри."
    }
    return descriptions.get(number, "Ты производишь уникальное впечатление.")

def get_karmic_description(number):
    descriptions = {
        13: "Кармический долг 13: в прошлом ты избегала труда. Сейчас важно научиться доводить дела до конца и не искать лёгких путей.",
        14: "Кармический долг 14: в прошлом ты злоупотребляла свободой. Сейчас важно найти баланс между обязательствами и независимостью.",
        16: "Кармический долг 16: в прошлом было высокомерие. Сейчас важно научиться смирению и принятию.",
        19: "Кармический долг 19: в прошлом ты злоупотребляла властью. Сейчас важно научиться опираться на других и доверять."
    }
    return descriptions.get(number, "У тебя нет кармического долга.")

def get_peak_description(number, peak_num):
    descriptions = {
        1: {1: "Первый пик — время учиться самостоятельности. Ты рано поняла, что рассчитывать можно только на себя.",
            2: "Второй пик — стань лидером. Придётся брать управление в свои руки.",
            3: "Третий пик — время новых начинаний. Открой своё дело или проект.",
            4: "Четвёртый пик — ты на вершине. Делись опытом и веди за собой."},
        2: {1: "Первый пик — учись сотрудничать. Ты поняла, что вместе — сила.",
            2: "Второй пик — время партнёрства. Важные отношения войдут в твою жизнь.",
            3: "Третий пик — дипломатия станет твоим главным оружием.",
            4: "Четвёртый пик — ты станешь мудрым советником для многих."},
        3: {1: "Первый пик — раскрой творческий потенциал. Не прячь свои таланты.",
            2: "Второй пик — время самовыражения. Пиши, говори, твори.",
            3: "Третий пик — твоё творчество принесёт плоды.",
            4: "Четвёртый пик — ты станешь источником вдохновения для других."},
        4: {1: "Первый пик — учись дисциплине. Построй свой фундамент.",
            2: "Второй пик — время усердной работы. Не сдавайся на полпути.",
            3: "Третий пик — твои усилия окупятся сторицей.",
            4: "Четвёртый пик — ты построишь то, что останется после тебя."},
        5: {1: "Первый пик — учись адаптироваться. Перемены — твоя стихия.",
            2: "Второй пик — время свободы. Путешествия, новые горизонты.",
            3: "Третий пик — рискни. Сейчас или никогда.",
            4: "Четвёртый пик — ты обретёшь истинную свободу."},
        6: {1: "Первый пик — учись заботиться. Семья и близкие — твоя опора.",
            2: "Второй пик — время ответственности. Не бойся её.",
            3: "Третий пик — твоя забота вернётся сторицей.",
            4: "Четвёртый пик — ты станешь хранительницей рода."},
        7: {1: "Первый пик — учись слушать себя. Тишина — твой учитель.",
            2: "Второй пик — время глубоких размышлений. Найди свой смысл.",
            3: "Третий пик — твоя мудрость будет востребована.",
            4: "Четвёртый пик — ты станешь наставницей."},
        8: {1: "Первый пик — учись управлять ресурсами. Деньги любят счёт.",
            2: "Второй пик — время строить карьеру. Ты на подъёме.",
            3: "Третий пик — финансовый расцвет. Инвестируй с умом.",
            4: "Четвёртый пик — ты достигнешь вершины."},
        9: {1: "Первый пик — учись состраданию. Мир больше, чем ты.",
            2: "Второй пик — время служения. Помогай тем, кто слабее.",
            3: "Третий пик — твоя доброта изменит мир вокруг.",
            4: "Четвёртый пик — ты оставишь светлый след."}
    }
    return descriptions.get(number, {}).get(peak_num, "Этот период принесёт новый опыт.")

def get_personal_year_description(number, year=None):
    """Описание личного года. Если year не передан — берётся текущий (MSK)."""
    if year is None:
        from utils.helpers import now_msk
        year = now_msk().year
    descriptions = {
        1: f"{year} — твой год начинаний. Сажай семена: новые проекты, знакомства, идеи. Всё, что начнёшь сейчас, принесёт плоды в будущем.",
        2: f"{year} — твой год терпения и партнёрства. Не форсируй события. Строй мосты, а не стены.",
        3: f"{year} — твой год творчества и радости. Общайся, твори, сияй. Твоя энергия притянет нужных людей.",
        4: f"{year} — твой год труда и порядка. Заложи фундамент на будущее. Дисциплина сейчас = свобода потом.",
        5: f"{year} — твой год перемен. Не бойся нового: переезд, смена работы, путешествия. Ветер дует в твою сторону.",
        6: f"{year} — твой год семьи и заботы. Укрепи тыл, наведи уют. Любовь — твоя главная валюта.",
        7: f"{year} — твой год познания себя. Замедлись, читай, медитируй. Ответы придут в тишине.",
        8: f"{year} — твой год урожая. Пожинай плоды прошлых усилий. Финансы и карьера на подъёме.",
        9: f"{year} — твой год завершений. Отпусти старое, что тянет назад. Готовься к новому циклу."
    }
    return descriptions.get(number, f"{year} год принесёт тебе новый опыт.")

def get_cell_name(number):
    names = {
        1: "Характер, воля, эго",
        2: "Энергия, харизма",
        3: "Интерес к науке",
        4: "Здоровье, тело",
        5: "Логика, интуиция",
        6: "Труд, мастерство",
        7: "Удача, везение",
        8: "Долг, ответственность",
        9: "Память, ум, интеллект"
    }
    return names.get(number, "")

def get_cell_description(number, count):
    cells = {
        1: {0: "Ты зависишь от мнения других. Учись слышать свой голос.",
            1: "Ты знаешь себе цену, но иногда эгоизм берёт верх.",
            2: "Твоя самооценка колеблется. Доверяй себе больше.",
            3: "Сильная воля и лидерские качества. Ты умеешь добиваться своего.",
            4: "Ты прирождённый лидер. Главное — не стать деспотичной.",
            5: "Твой характер — ураган. Учись мягкости."},
        2: {0: "Энергии мало. Береги себя: больше отдыха, меньше суеты.",
            1: "Энергии хватает на главное. Планируй отдых заранее.",
            2: "Ты совместима с большинством людей. Хорошая энергетика.",
            3: "У тебя есть экстрасенсорные способности. Развивай их."},
        3: {0: "Ты гуманитарий по природе. Цифры — не твоя стихия.",
            1: "Ты аккуратна и любишь порядок в делах.",
            2: "Склонность к точным наукам. Хороший аналитический ум.",
            3: "Мощный интеллект, но есть риск зацикливаться на мелочах."},
        4: {0: "Здоровье требует внимания. Не запускай профилактику.",
            1: "Здоровье среднее. Спорт как дисциплина — твой выбор.",
            2: "Крепкое здоровье. Ты редко болеешь.",
            3: "Отличная физическая форма от природы."},
        5: {0: "Интуиция молчит. Доверяй логике и расчёту.",
            1: "Интуиция есть, но ты ей не доверяешь. А зря.",
            2: "Развитая интуиция. Слушай первое впечатление.",
            3: "Ты ясновидящая. Твои предчувствия сбываются."},
        6: {0: "Физический труд — не твоё. Твоя сфера — интеллект.",
            1: "Ты трудишься ради близких. Для себя — лень.",
            2: "Ты трудоголик. Не забывай отдыхать.",
            3: "Одержимость работой. Береги нервы."},
        7: {0: "Удача не падает с неба. Всё только через труд.",
            1: "Ты удачлива, но ленива. Проснись!",
            2: "Везение — твоё второе имя. Не злоупотребляй.",
            3: "Ты под защитой ангелов. Доверяй потоку."},
        8: {0: "Ты не терпишь несправедливости, но прощать трудно.",
            1: "Ты терпима, но не безотказна. Здоровые границы.",
            2: "Ты очень добра и умеешь прощать. Люди это ценят.",
            3: "Твоя доброта безгранична. Не дай сесть на шею."},
        9: {0: "Память требует тренировки. Записывай важное.",
            1: "Нормальная память. Ты помнишь главное.",
            2: "Хорошая память и богатое воображение.",
            3: "Феноменальная память. Ты помнишь даже детали."}
    }
    return cells.get(number, {}).get(count, "")

def get_prompt_from_db(prompt_name):
    try:
        from database.db import get_db
        with get_db() as conn:
            row = conn.execute("SELECT content FROM prompts WHERE name = ?", (prompt_name,)).fetchone()
            if row:
                return row['content']
    except:
        pass
    return ""

# ============================================
# НАТАЛЬНАЯ КАРТА
# ============================================

def calculate_natal_chart(birth_date, birth_time='12:00', birth_place='', detailed=False, lat=None, lng=None):
    import math
    
    from utils.helpers import now_msk
    try:
        dt_check = datetime.strptime(birth_date, '%Y-%m-%d')
        if dt_check > now_msk().replace(tzinfo=None):
            return {"error": "Дата рождения не может быть в будущем"}
    except (ValueError, TypeError):
        return {"error": "Неверный формат даты"}
    
    try:
        import swisseph as swe
        
        # Путь к эфемеридам
        ephe_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'ephemeris')
        if os.path.exists(ephe_path):
            swe.set_ephe_path(ephe_path)
        
        dt = datetime.strptime(birth_date, '%Y-%m-%d')
        time_parts = birth_time.split(':')
        hour = int(time_parts[0]) if len(time_parts) > 0 else 12
        minute = int(time_parts[1]) if len(time_parts) > 1 else 0
        
        # Если координаты переданы с фронта (пользователь выбрал город из автокомплита) — используем их.
        # Иначе — пробуем Nominatim. Если не удалось — возвращаем ошибку,
        # чтобы не строить карту для другого города молча.
        if lat is None or lng is None:
            if birth_place:
                try:
                    import requests
                    resp = requests.get(
                        f'https://nominatim.openstreetmap.org/search?q={birth_place}&format=json&limit=1',
                        headers={'User-Agent': 'NumerApp/1.0'},
                        timeout=5
                    )
                    data = resp.json()
                    if data:
                        lat = float(data[0]['lat'])
                        lng = float(data[0]['lon'])
                except Exception:
                    pass
        
        if lat is None or lng is None:
            return {"error": "Не удалось определить координаты места рождения. Проверьте название города или укажите координаты вручную."}
        
        # Определяем часовой пояс по координатам и приводим к UTC
        from timezonefinder import TimezoneFinder
        import pytz

        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lat=lat, lng=lng)
        if tz_name:
            tz = pytz.timezone(tz_name)
            local_dt = dt.replace(hour=hour, minute=minute)
            local_dt = tz.localize(local_dt)
            utc_dt = local_dt.astimezone(pytz.UTC)
            jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, 
                            utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0)
        else:
            jd = swe.julday(dt.year, dt.month, dt.day, hour + minute / 60.0)
        
        sign_names = ['Овен', 'Телец', 'Близнецы', 'Рак', 'Лев', 'Дева',
                      'Весы', 'Скорпион', 'Стрелец', 'Козерог', 'Водолей', 'Рыбы']
        # Единый источник ELEMENT_MAP — utils.constants
        from utils.constants import ELEMENT_MAP as element_map
        
        def format_position(lon):
            sign_idx = int(lon / 30) % 12
            lon_in_sign = lon % 30
            return {
                'sign': sign_names[sign_idx],
                'degree': int(lon_in_sign),
                'minute': int((lon_in_sign - int(lon_in_sign)) * 60),
                'lon': round(lon, 6),
                'element': element_map.get(sign_names[sign_idx], '')
            }
        
        planet_codes = {
            'sun': (swe.SUN, 'Солнце', '☉'),
            'moon': (swe.MOON, 'Луна', '☽'),
            'mercury': (swe.MERCURY, 'Меркурий', '☿'),
            'venus': (swe.VENUS, 'Венера', '♀'),
            'mars': (swe.MARS, 'Марс', '♂'),
            'jupiter': (swe.JUPITER, 'Юпитер', '♃'),
            'saturn': (swe.SATURN, 'Сатурн', '♄'),
            'uranus': (swe.URANUS, 'Уран', '♅'),
            'neptune': (swe.NEPTUNE, 'Нептун', '♆'),
            'pluto': (swe.PLUTO, 'Плутон', '♇'),
            'mean_node': (swe.MEAN_NODE, 'Северный узел', '☊'),
            'chiron': (swe.CHIRON, 'Хирон', '⚷'),
        }
        
        result = {
            'success': True,
            'birth_date': birth_date,
            'birth_time': birth_time,
            'birth_place': birth_place,
            'lat': lat, 'lng': lng,
            'planets': {}
        }
        
        # Расчёт планет
        for key, (code, name, emoji) in planet_codes.items():
            try:
                xx, ret = swe.calc_ut(jd, code, swe.FLG_SWIEPH)
                lon = xx[0]
                retrograde = ret < 0
                
                data = {'emoji': emoji, 'name': name, 'retrograde': retrograde, **format_position(lon)}
                
                if key == 'sun':
                    result['sun'] = data
                elif key == 'moon':
                    result['moon'] = data
                elif key == 'mean_node':
                    data['retrograde'] = True  # Узлы всегда ретроградны
                    result['north_node'] = data
                    south_lon = (lon + 180) % 360
                    result['south_node'] = {'emoji': '☋', 'name': 'Южный узел', 'retrograde': True, **format_position(south_lon)}
                elif key == 'chiron':
                    result['chiron'] = data
                else:
                    result['planets'][name] = data
            except Exception as e:
                logging.getLogger(__name__).warning("Natal: planet %s calc failed: %s", name, e)
        
        # Дома Плацидуса
        try:
            houses_raw, asc_raw = swe.houses(jd, lat, lng, b'P')
            result['ascendant'] = {'emoji': '↑', 'name': 'Асцендент', **format_position(asc_raw[0])}
            result['mc'] = {'emoji': 'MC', 'name': 'Середина неба', **format_position(houses_raw[9])}
            
            house_names = ['Личность', 'Финансы', 'Общение', 'Семья', 'Творчество',
                          'Работа', 'Партнерство', 'Трансформация', 'Путешествия',
                          'Карьера', 'Дружба', 'Подсознание']
            houses = []
            for i in range(12):
                houses.append({'number': i + 1, 'name': house_names[i], **format_position(houses_raw[i])})
            result['houses'] = houses
        except Exception as e:
            print(f"Houses error: {e}")
            result['ascendant'] = {'emoji': '↑', 'name': 'Асцендент', 'sign': '—', 'degree': 0, 'minute': 0, 'lon': 0, 'element': ''}
            result['mc'] = {'emoji': 'MC', 'name': 'Середина неба', 'sign': '—', 'degree': 0, 'minute': 0, 'lon': 0, 'element': ''}
            result['houses'] = []
        
        # Проверка ретроградности через суточную скорость
        jd_tomorrow = jd + 1.0
        for key, (code, name, emoji) in planet_codes.items():
            if key in ['sun', 'moon', 'mean_node', 'chiron']:
                continue
            try:
                xx_today, ret_today = swe.calc_ut(jd, code, swe.FLG_SWIEPH)
                xx_tomorrow, ret_tomorrow = swe.calc_ut(jd_tomorrow, code, swe.FLG_SWIEPH)
                speed = xx_tomorrow[0] - xx_today[0]
                if speed > 180:
                    speed -= 360
                elif speed < -180:
                    speed += 360
                is_retro = speed < 0
                
                if name in result['planets']:
                    result['planets'][name]['retrograde'] = is_retro
            except Exception as e:
                logging.getLogger(__name__).warning("Natal: retrograde check failed for %s: %s", name, e)
        
        # Хирон
        if 'chiron' in result:
            try:
                xx_today, _ = swe.calc_ut(jd, swe.CHIRON, swe.FLG_SWIEPH)
                xx_tomorrow, _ = swe.calc_ut(jd_tomorrow, swe.CHIRON, swe.FLG_SWIEPH)
                speed = xx_tomorrow[0] - xx_today[0]
                if speed > 180: speed -= 360
                elif speed < -180: speed += 360
                result['chiron']['retrograde'] = speed < 0
            except:
                pass
        
        return result
        
    except ImportError:
        print("pyswisseph not installed, using flatlib fallback")
    except Exception as e:
        print(f"Natal chart error: {e}")
        import traceback
        traceback.print_exc()
    
    # Fallback
    basic_result = {
        "message": "Для точного расчёта натальной карты мы работаем над интеграцией астрологических таблиц.",
        "birth_date": birth_date, "birth_time": birth_time, "birth_place": birth_place,
    }
    if detailed:
        ai_text = ai_natal_chart(name="", birth_date=birth_date, birth_time=birth_time, birth_place=birth_place)
        if ai_text:
            if isinstance(ai_text, dict):
                basic_result.update(ai_text)
            else:
                basic_result["ai_interpretation"] = ai_text
    return basic_result
    
def render_natal_chart_svg(chart_data):
    """
    Генерирует читаемое SVG-колесо натальной карты.
    Показывает: знаки зодиака, дома Плацидуса, планеты с иконками, аспектные линии, углы ASC/DSC/MC/IC.
    """
    import math

    if not chart_data or not chart_data.get('success'):
        return '<div style="text-align:center;color:var(--color-text-lighter);padding:40px;">Недостаточно данных для построения карты</div>'

    W, H = 400, 400
    CX, CY = 200, 200
    R_BG = 194
    R_SIGN = 174
    R_TICK_OUTER = 188
    R_TICK_INNER = 156
    R_HOUSE_INNER = 50
    R_HOUSE_OUTER = 184
    R_ASPECT = 128
    R_PLANET_ORBIT = 128
    R_PLANET_LABEL = 196

    GREEN = 'rgba(120,200,140,'
    RED = 'rgba(220,120,120,'
    GOLD = 'rgba(210,161,125,'

    from utils.constants import ZODIAC_SIGNS

    def polar(r, angle_deg):
        rad = math.radians(angle_deg - 90)
        return CX + r * math.cos(rad), CY + r * math.sin(rad)

    # --- Сбор планет ---
    planets = []

    def add_planet(key, name, emoji, data):
        if data and data.get('lon') is not None:
            planets.append({'key': key, 'name': name, 'emoji': emoji,
                            'lon': float(data['lon']), 'sign': data.get('sign', ''),
                            'degree': data.get('degree', 0), 'minute': data.get('minute', 0)})

    add_planet('sun', 'Солнце', '☉', chart_data.get('sun'))
    add_planet('moon', 'Луна', '☽', chart_data.get('moon'))
    for p_name, p_data in chart_data.get('planets', {}).items():
        key_map = {'Меркурий': 'mercury', 'Венера': 'venus', 'Марс': 'mars',
                   'Юпитер': 'jupiter', 'Сатурн': 'saturn', 'Уран': 'uranus',
                   'Нептун': 'neptune', 'Плутон': 'pluto'}
        add_planet(key_map.get(p_name, p_name.lower()), p_name, p_data.get('emoji', ''), p_data)

    # --- Аспекты ---
    def angle_diff(a, b):
        d = abs(a - b) % 360
        return min(d, 360 - d)

    def get_aspect(angle):
        if angle <= 8:
            return ('conjunction', 0, GREEN)
        if abs(angle - 60) <= 6:
            return ('sextile', 60, GREEN)
        if abs(angle - 90) <= 6:
            return ('square', 90, RED)
        if abs(angle - 120) <= 8:
            return ('trine', 120, GREEN)
        if abs(angle - 180) <= 8:
            return ('opposition', 180, RED)
        return None

    aspect_lines = []
    for i in range(len(planets)):
        for j in range(i + 1, len(planets)):
            diff = angle_diff(planets[i]['lon'], planets[j]['lon'])
            asp = get_aspect(diff)
            if asp:
                aspect_lines.append({'p1': i, 'p2': j, 'color': asp[2], 'diff': round(diff, 1)})

    # --- SVG ---
    svg = []
    svg.append(f'<svg class="nr-wheel" viewBox="0 0 {W} {H}" role="img" aria-label="Натальная карта">')
    svg.append('<defs>')
    svg.append(f'<radialGradient id="nrGlow" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="rgba(210,161,125,0.08)"/><stop offset="100%" stop-color="rgba(210,161,125,0)"/></radialGradient>')
    svg.append('</defs>')

    # Фон
    svg.append(f'<circle cx="{CX}" cy="{CY}" r="{R_BG}" fill="url(#nrGlow)"/>')
    # Кольца
    svg.append(f'<circle cx="{CX}" cy="{CY}" r="{R_TICK_OUTER}" fill="none" stroke="rgba(210,161,125,0.4)" stroke-width="1"/>')
    svg.append(f'<circle cx="{CX}" cy="{CY}" r="{R_TICK_INNER}" fill="none" stroke="rgba(210,161,125,0.25)" stroke-width="1"/>')
    svg.append(f'<circle cx="{CX}" cy="{CY}" r="{R_HOUSE_INNER}" fill="none" stroke="rgba(210,161,125,0.2)" stroke-width="1"/>')

    # Деления градусов (каждые 2°)
    svg.append('<g stroke="rgba(210,161,125,0.4)">')
    for deg in range(0, 360, 2):
        x1, y1 = polar(R_TICK_INNER, deg)
        x2, y2 = polar(R_TICK_OUTER, deg)
        major = (deg % 10 == 0)
        sw = 1 if major else 0.5
        op = 0.5 if major else 0.18
        svg.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke-width="{sw}" opacity="{op}"/>')
    svg.append('</g>')

    # Дома (линии от внутреннего кольца до внешнего)
    houses = chart_data.get('houses', [])
    if houses:
        svg.append('<g stroke="rgba(210,161,125,0.5)" stroke-width="1.2">')
        for h in houses:
            lon = h.get('lon', 0)
            x, y = polar(R_HOUSE_OUTER, lon)
            svg.append(f'<line x1="{CX:.2f}" y1="{CY:.2f}" x2="{x:.2f}" y2="{y:.2f}"/>')
        svg.append('</g>')

    # Номера домов
    if houses and len(houses) == 12:
        R_HOUSE_NUM = (R_HOUSE_INNER + R_TICK_INNER) / 2
        for i, h in enumerate(houses):
            next_h = houses[(i + 1) % 12]
            mid = (h['lon'] + next_h['lon']) / 2
            if next_h['lon'] < h['lon']:
                mid = (h['lon'] + next_h['lon'] + 360) / 2
            if mid >= 360:
                mid -= 360
            nx, ny = polar(R_HOUSE_NUM, mid)
            svg.append(f'<text x="{nx:.2f}" y="{ny:.2f}" fill="#d4879a" font-size="10" font-weight="600" text-anchor="middle" dominant-baseline="middle">{h.get("number", i+1)}</text>')

    # Знаки зодиака по кругу (порядок ZODIAC_SIGNS — от Овна к Рыбам)
    for i, sign in enumerate(ZODIAC_SIGNS):
        angle = i * 30 + 15
        x, y = polar(R_SIGN, angle)
        icon_path = f'/static/images/horoscope/{sign["key"]}.svg'
        svg.append(f'<image href="{icon_path}" x="{x-10:.2f}" y="{y-10:.2f}" width="20" height="20" opacity="0.85"/>')

    # Аспектные линии
    if aspect_lines:
        svg.append('<g fill="none">')
        for a in aspect_lines:
            p1 = planets[a['p1']]
            p2 = planets[a['p2']]
            x1, y1 = polar(R_ASPECT, p1['lon'])
            x2, y2 = polar(R_ASPECT, p2['lon'])
            quality = 1.0 - (a['diff'] / 8.0)
            sw = 0.5 + quality * 1.5
            op = 0.25 + quality * 0.35
            svg.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{a["color"]}{op:.2f})" stroke-width="{sw:.2f}" stroke-linecap="round"/>')
        svg.append('</g>')

    # Планеты
    for p in planets:
        px, py = polar(R_PLANET_ORBIT, p['lon'])
        # Линия-указатель к краю
        lx, ly = polar(R_TICK_OUTER, p['lon'])
        svg.append(f'<g class="nr-wheel-planet">')
        svg.append(f'<line x1="{px:.2f}" y1="{py:.2f}" x2="{lx:.2f}" y2="{ly:.2f}" stroke="rgba(210,161,125,0.5)" stroke-width="1"/>')
        # Иконка планеты
        icon_file = f'/static/images/natal/planets/{p["key"]}.svg'
        svg.append(f'<image href="{icon_file}" x="{px-12:.2f}" y="{py-12:.2f}" width="24" height="24"/>')
        # Подпись градусов у внешнего края
        lbl_x, lbl_y = polar(R_PLANET_LABEL, p['lon'])
        svg.append(f'<text x="{lbl_x:.2f}" y="{lbl_y:.2f}" fill="#ffd54f" font-size="7" text-anchor="middle" dominant-baseline="middle">{p["degree"]}°{p["minute"]:02d}\'</text>')
        svg.append('</g>')

    # ASC / MC / DSC / IC
    asc = chart_data.get('ascendant', {})
    mc = chart_data.get('mc', {})
    if asc:
        asc_lon = asc.get('lon', 0)
        dsc_lon = (asc_lon + 180) % 360
        for label, lon, color in [('As', asc_lon, '#ffd54f'), ('Ds', dsc_lon, '#d4879a')]:
            x, y = polar(R_SIGN + 14, lon)
            svg.append(f'<text x="{x:.2f}" y="{y:.2f}" fill="{color}" font-size="10" font-weight="700" text-anchor="middle" dominant-baseline="middle">{label}</text>')
    if mc:
        mc_lon = mc.get('lon', 0)
        ic_lon = (mc_lon + 180) % 360
        for label, lon, color in [('Mc', mc_lon, '#ffd54f'), ('Ic', ic_lon, '#d4879a')]:
            x, y = polar(R_SIGN + 14, lon)
            svg.append(f'<text x="{x:.2f}" y="{y:.2f}" fill="{color}" font-size="10" font-weight="700" text-anchor="middle" dominant-baseline="middle">{label}</text>')

    svg.append('</svg>')
    return '\n'.join(svg)

# ============================================
# СОВМЕСТИМОСТЬ
# ============================================

def calculate_compatibility(person1, person2, detailed=False, skip_ai_interpretation=False, user_id=None):
    import hashlib

    name1 = person1.get('name', 'Партнёр 1').strip()
    name2 = person2.get('name', 'Партнёр 2').strip()
    birth1 = person1.get('birth_date', '')
    birth2 = person2.get('birth_date', '')
    
    # Проверка дат рождения
    from utils.helpers import now_msk
    for birth_val, label in [(birth1, name1), (birth2, name2)]:
        if birth_val:
            try:
                dt_check = datetime.strptime(birth_val, '%Y-%m-%d')
                if dt_check > now_msk().replace(tzinfo=None):
                    return {"error": f"Дата рождения {label} не может быть в будущем"}
            except:
                pass

    name_normalization = {
        "саша": "александр", "саня": "александр", "шура": "александр", "сашка": "александр",
        "сашуля": "александр", "санёк": "александр", "шурик": "александр", "алекс": "александр",
        "лёша": "алексей", "алёша": "алексей", "лёшка": "алексей", "лёха": "алексей",
        "настя": "анастасия", "настенька": "анастасия", "настюша": "анастасия",
        "аня": "анна", "анечка": "анна", "анюта": "анна",
        "андрюша": "андрей", "андрюха": "андрей", "андрейка": "андрей",
        "тоша": "антон", "антошка": "антон", "тоха": "антон",
        "боря": "борис", "борька": "борис", "боб": "борис",
        "валя": "валентин", "валька": "валентин",
        "валера": "валерий", "лерка": "валерия",
        "варя": "варвара", "варюша": "варвара",
        "вася": "василий", "васька": "василий",
        "верочка": "вера",
        "витя": "виктор", "витька": "виктор",
        "вика": "виктория", "викуся": "виктория",
        "вова": "владимир", "володя": "владимир",
        "влад": "владислав", "слава": "владислав",
        "галя": "галина",
        "гена": "геннадий", "генка": "геннадий",
        "гоша": "георгий", "жора": "георгий", "егор": "георгий",
        "гриша": "григорий",
        "даня": "даниил", "данила": "даниил",
        "даша": "дарья", "дашка": "дарья",
        "дениска": "денис",
        "дима": "дмитрий", "димка": "дмитрий",
        "женя": "евгений", "женька": "евгений",
        "катя": "екатерина", "катюша": "екатерина",
        "лена": "елена", "ленка": "елена", "алёна": "елена",
        "лиза": "елизавета",
        "ваня": "иван", "ванька": "иван",
        "игорёк": "игорь",
        "илюша": "илья",
        "ира": "ирина", "ирка": "ирина",
        "киря": "кирилл",
        "костя": "константин", "костик": "константин",
        "кристи": "кристина",
        "ксюша": "ксения", "ксюшка": "ксения",
        "лара": "лариса",
        "лёня": "леонид", "лёнька": "леонид",
        "лида": "лидия",
        "люба": "любовь",
        "люда": "людмила", "мила": "людмила",
        "макс": "максим",
        "рита": "маргарита", "марго": "маргарита",
        "маша": "мария", "машка": "мария",
        "маришка": "марина",
        "миша": "михаил", "мишка": "михаил",
        "надя": "надежда",
        "наташа": "наталья", "наташка": "наталья",
        "никитос": "никита",
        "коля": "николай", "колька": "николай",
        "оксанка": "оксана",
        "олежка": "олег",
        "оля": "ольга", "олька": "ольга",
        "паша": "павел", "пашка": "павел",
        "петя": "пётр", "петька": "пётр",
        "поля": "полина",
        "рома": "роман", "ромка": "роман",
        "света": "светлана", "светка": "светлана",
        "серёжа": "сергей", "серёга": "сергей",
        "соня": "софья", "сонечка": "софья",
        "стас": "станислав",
        "стёпа": "степан",
        "тася": "таисия",
        "тома": "тамара",
        "таня": "татьяна", "танька": "татьяна", "танюша": "татьяна",
        "федя": "фёдор",
        "юля": "юлия", "юлька": "юлия",
        "юра": "юрий", "юрка": "юрий",
        "яночка": "яна",
        "ярик": "ярослав",
    }

    def normalize_name(name):
        name_lower = name.lower().strip()
        return name_normalization.get(name_lower, name_lower)

    normalized1 = normalize_name(name1)
    normalized2 = normalize_name(name2)

    pair = sorted([(normalized1, birth1), (normalized2, birth2)], key=lambda x: x[0] + x[1])
    hash_input = f"{pair[0][0]}|{pair[0][1]}|{pair[1][0]}|{pair[1][1]}"
    hash_value = hashlib.sha256(hash_input.encode()).hexdigest()
    hash_int = int(hash_value[:8], 16)
    compatibility_score = 60 + (hash_int % 39)

    verdict = "Отличная совместимость!" if compatibility_score > 80 else "Хорошая совместимость"

    basic_result = {
        "person1": name1,
        "person2": name2,
        "compatibility_percent": compatibility_score,
        "verdict": verdict,
    }

    if detailed and detailed != 'guest':
        # Краткие описания для бесплатного тарифа
        basic_result["criteria_brief"] = {
            "Совместимость по именам": f"Имена {name1} и {name2} создают уникальную вибрацию.",
            "Совместимость по дате рождения": "Даты рождения определяют жизненные ритмы.",
            "Число судьбы": "Число судьбы показывает кармическую задачу союза.",
            "Кармическая разница": "Разница в датах указывает на уроки.",
            "Любовь": "Эмоциональная связь и романтический потенциал.",
            "Совместный быт": "Насколько комфортно вместе в повседневной жизни.",
            "Финансы": "Денежная энергия пары и отношение к ресурсам."
        }

        # ======= ДОБАВИТЬ: расчёт реальных данных для тизеров =======
        real_data = ""
        try:
            # Считаем числа судьбы
            def name_to_number(n):
                letter_map = {
                    'а':1,'б':2,'в':3,'г':4,'д':5,'е':6,'ё':7,'ж':8,'з':9,
                    'и':1,'й':2,'к':3,'л':4,'м':5,'н':6,'о':7,'п':8,'р':9,
                    'с':1,'т':2,'у':3,'ф':4,'х':5,'ц':6,'ч':7,'ш':8,'щ':9,
                    'ъ':1,'ы':2,'ь':3,'э':4,'ю':5,'я':6
                }
                def reduce_n(n):
                    while n > 9:
                        n = sum(int(d) for d in str(n))
                    return n
                return reduce_n(sum(letter_map.get(c.lower(), 0) for c in n if c.isalpha()))
            
            n1_num = name_to_number(name1)
            n2_num = name_to_number(name2)
            real_data += f"Число имени {name1}: {n1_num}. Число имени {name2}: {n2_num}. "
            
            # Считаем числа по датам (сокращаем мастер-числа, как в платном ответе)
            def reduce_num(n):
                while n > 9:
                    n = sum(int(d) for d in str(n))
                return n
            
            if birth1:
                b1_sum = sum(int(d) for d in birth1.replace('-', ''))
                b1 = reduce_num(b1_sum)
                real_data += f"Число судьбы {name1}: {b1}. "
            if birth2:
                b2_sum = sum(int(d) for d in birth2.replace('-', ''))
                b2 = reduce_num(b2_sum)
                real_data += f"Число судьбы {name2}: {b2}. "
            
            # Разница чисел судьбы
            if birth1 and birth2:
                real_data += f"Разница чисел судьбы: {abs(b1 - b2)}. "
            
            # Разница в годах
            if birth1 and birth2:
                y1 = int(birth1[:4])
                y2 = int(birth2[:4])
                year_diff = abs(y1 - y2)
                real_data += f"Разница в возрасте: {year_diff} лет. "
            
            # Стихии по году
            if birth1:
                y1 = int(birth1[:4])
                elements = ['Металл','Металл','Вода','Вода','Дерево','Дерево','Огонь','Огонь','Земля','Земля']
                animals = ['Крыса','Бык','Тигр','Кролик','Дракон','Змея','Лошадь','Коза','Обезьяна','Петух','Собака','Свинья']
                e1 = elements[(y1 - 1900) % 10]
                a1 = animals[(y1 - 1900) % 12]
                real_data += f"{name1}: {e1} {a1}. "
            if birth2:
                y2 = int(birth2[:4])
                e2 = elements[(y2 - 1900) % 10]
                a2 = animals[(y2 - 1900) % 12]
                real_data += f"{name2}: {e2} {a2}. "
        except:
            pass

        # AI-персонализация кратких описаний
        criteria_keys = [
            "Совместимость по именам",
            "Совместимость по дате рождения",
            "Число судьбы",
            "Кармическая разница",
            "Любовь",
            "Совместный быт",
            "Финансы"
        ]

        ai_brief = None
        if not skip_ai_interpretation:
            ai_brief = ask_deepseek(
                system_prompt="""Ты — астролог, который пишет тизеры для бесплатной версии сайта. Твоя цель — дать 80% информации и 20% интриги так, чтобы человек ЗАХОТЕЛ заплатить за полный разбор.

        СТРУКТУРА ОТВЕТА — СТРОГО 7 строк, каждая строка соответствует СВОЕМУ критерию. НЕ МЕНЯЙ ПОРЯДОК:

        Строка 1 — Совместимость по именам
        Строка 2 — Совместимость по дате рождения
        Строка 3 — Число судьбы
        Строка 4 — Кармическая разница
        Строка 5 — Любовь
        Строка 6 — Совместный быт
        Строка 7 — Финансы

        ФОРМАТ КАЖДОЙ СТРОКИ — ровно 3 предложения:

        Предложение 1 — КОНКРЕТНЫЙ ФАКТ строго по теме критерия. Для имён — про имена и их числа. Для дат — про даты и стихии. Для числа судьбы — про числа судьбы. Для кармы — про кармическую разницу. Для любви — про чувства. Для быта — про быт. Для финансов — про деньги.

        Предложение 2 — ЧТО ЭТО ЗНАЧИТ НА ПРАКТИКЕ. Один конкретный пример, строго связанный с темой критерия.

        Предложение 3 — ИНТРИГА. Вопрос, заканчивающийся на «?», строго по теме критерия.

        ПРИМЕР (для критерия «Число судьбы»):
        «Число судьбы Андрея — 9, Татьяны — 1. Разница в 8 единиц означает, что один всегда начинает, другой — завершает. В какой сфере жизни они меняются ролями и почему это может разрушить союз?»

        ЖЁСТКИЕ ПРАВИЛА:
        - Каждая строка СТРОГО соответствует своему критерию. Строка 1 — только про имена. Строка 3 — только про число судьбы. НЕ ПУТАЙ.
        - ЗАПРЕЩЕНЫ метафоры и поэзия. ТОЛЬКО ПРЯМОЙ ТЕКСТ.
        - ЗАПРЕЩЕНЫ обращения «ты», «твой», «вы», «ваш».
        - Каждый тизер — ровно 3 предложения.
        - Последнее предложение — ВОПРОС со знаком «?».
        - Без эмодзи, без кавычек, без нумерации.
        - Ровно 7 строк.""",
                user_prompt=f"Пара: {name1} (рожд. {birth1}) и {name2} (рожд. {birth2}). Совместимость: {compatibility_score}%. РЕАЛЬНЫЕ ДАННЫЕ (используй только их): {real_data} Напиши 7 тизеров строго по порядку: имена, даты рождения, число судьбы, карма, любовь, быт, финансы. Каждая строка — про свой критерий.",
                temperature=0.9,
                user_id=user_id
            )
            if ai_brief:
                lines = [l.strip() for l in ai_brief.split('\n') if l.strip()]
                for i, key in enumerate(criteria_keys):
                    if i < len(lines):
                        basic_result["criteria_brief"][key] = lines[i]

        # Полный AI-разбор для Провидца и Оракула + тизеры на его основе
        # skip_ai_interpretation=True — вызывающий роут сам сделает разбор через ai_compatibility_full
        if detailed == 'plamya' and not skip_ai_interpretation:
            ai_text = ai_compatibility(
                name1=name1, name2=name2,
                birth1=birth1, birth2=birth2,
                score=compatibility_score,
                user_id=user_id
            )
            if ai_text and isinstance(ai_text, dict):
                basic_result["ai_interpretation"] = ai_text
                
                # Генерируем тизеры на основе полного разбора
                teaser_prompt = """Ты — мастер эмоциональных текстов. Ниже — ПОЛНЫЙ разбор совместимости пары по 7 критериям. На его основе напиши 7 тизеров — по одному на каждый критерий.

СТРОГОЕ СООТВЕТСТВИЕ (не меняй порядок):
Строка 1 — Совместимость по именам (на основе секции "names")
Строка 2 — Совместимость по дате рождения (на основе секции "birth")
Строка 3 — Число судьбы (на основе секции "destiny")
Строка 4 — Кармическая разница (на основе секции "karma")
Строка 5 — Любовь (на основе секции "love")
Строка 6 — Совместный быт (на основе секции "household")
Строка 7 — Финансы (на основе секции "finance")

ФОРМАТ КАЖДОГО ТИЗЕРА — ровно 3 предложения:

Предложение 1 — КОНКРЕТНЫЙ ФАКТ из полного разбора. Бери ТОЛЬКО то, что реально есть в тексте секции. Цифры, имена, стихии, числа.

Предложение 2 — КОРОТКИЙ ПРИМЕР из жизни, основанный на фактах из полного разбора. Одна конкретная ситуация, в которой проявляется эта особенность пары.

Предложение 3 — ЭМОЦИОНАЛЬНАЯ ИНТРИГА. Вопрос, который бьёт в самое сердце. Используй приёмы:
- Страх потери: «Что случится, когда...»
- Надежда: «Какой момент перевернёт...»
- Ревность: «Кто из них первым...»
- Тайна: «О чём молчат оба, когда...»
- Вызов: «Сколько ещё они смогут...»
- Судьба: «В какой день решится...»

Вопрос должен быть таким, чтобы человек НЕ МОГ не узнать ответ. Чтобы задело лично. Чтобы захотелось немедленно открыть полный разбор.

ПРИМЕР сильной интриги:
«Сколько ещё продлится этот брак, если они продолжат молчать об одном и том же?»
«Кто из них заплачет первым, когда рухнет этот тщательно выстроенный быт?»
«В какой момент Андрей поймёт, что Татьяна давно всё решила за него?»

ЖЁСТКИЕ ПРАВИЛА:
- Каждая строка СТРОГО соответствует своему критерию.
- Факты ТОЛЬКО из полного разбора. Не выдумывай того, чего нет в тексте.
- Без «ты», «твой», «вы», «ваш». Только имена или безлично.
- Без эмодзи. Без кавычек. Без нумерации.
- Каждый тизер — ровно 3 предложения.
- Последнее предложение — ВОПРОС со знаком «?», вызывающий эмоцию.
- Ровно 7 строк."""

                full_text_for_teaser = ""
                for key in ['names', 'birth', 'destiny', 'karma', 'love', 'household', 'finance']:
                    if key in ai_text:
                        full_text_for_teaser += f"{key}: {ai_text[key][:300]}\n"
                
                ai_teasers = ask_deepseek(
                    teaser_prompt,
                    f"Полный разбор:\n{full_text_for_teaser}\n\nНапиши 7 тизеров строго по порядку критериев. Факты бери ТОЛЬКО из полного разбора. Интрига должна быть сильной, эмоциональной, бьющей в сердце.",
                    temperature=0.95,
                    user_id=user_id
                )
                
                if ai_teasers:
                    teaser_lines = [l.strip() for l in ai_teasers.split('\n') if l.strip()]
                    criteria_keys = [
                        "Совместимость по именам",
                        "Совместимость по дате рождения", 
                        "Число судьбы",
                        "Кармическая разница",
                        "Любовь",
                        "Совместный быт",
                        "Финансы"
                    ]
                    for i, key in enumerate(criteria_keys):
                        if i < len(teaser_lines):
                            basic_result["criteria_brief"][key] = teaser_lines[i]

        # Вывод для Оракула
        if detailed == 'plamya':
            conclusion = ask_deepseek(
                system_prompt="Ты — астролог. Итоговый вывод 2-3 предложения. Тепло, с верой. Начни с фразы «Совместимость N% — это...»",
                user_prompt=f"Пара: {name1} и {name2}. Совместимость: {compatibility_score}%.",
                temperature=0.7,
                user_id=user_id
            )
            if conclusion:
                basic_result["conclusion"] = conclusion

    return basic_result

# ============================================
# ЛУННЫЙ КАЛЕНДАРЬ
# ============================================

def _get_lunar_core(date_str, timezone='Europe/Moscow'):
    import math
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
    except:
        from utils.helpers import now_msk
        dt = now_msk().replace(tzinfo=None)

    observer = ephem.Observer()
    try:
        import pytz
        tz = pytz.timezone(timezone)
        local_dt = tz.localize(datetime(dt.year, dt.month, dt.day, 12, 0, 0))
        observer.date = local_dt.strftime('%Y/%m/%d %H:%M:%S')
    except:
        observer.date = dt.strftime('%Y/%m/%d 12:00:00')

    moon = ephem.Moon()
    moon.compute(observer)

    prev_new_moon = ephem.previous_new_moon(dt.strftime('%Y/%m/%d'))
    lunar_day = int((ephem.Date(dt.strftime('%Y/%m/%d 12:00:00')) - prev_new_moon) / 1.0) + 1
    if lunar_day > 30:
        lunar_day = 1

    illumination = moon.moon_phase
    if lunar_day == 1 or illumination < 0.05:
        phase_name = "Новолуние"
    elif 2 <= lunar_day <= 7:
        phase_name = "Молодая Луна"
    elif lunar_day == 8:
        phase_name = "Первая четверть"
    elif 9 <= lunar_day <= 14:
        phase_name = "Прибывающая Луна"
    elif lunar_day == 15 or (0.48 <= illumination <= 0.52):
        phase_name = "Полнолуние"
    elif 16 <= lunar_day <= 21:
        phase_name = "Убывающая Луна"
    elif lunar_day == 22:
        phase_name = "Последняя четверть"
    else:
        phase_name = "Старая Луна"

    from utils.constants import ZODIAC_NAMES_RU
    # Знак Луны определяется по эклиптической долготе, а не по прямому восхождению.
    # Разница для Луны достигает ~2-3°, что критично на границах знаков.
    # Порядок ZODIAC_NAMES_RU — от Овна к Рыбам, что соответствует индексации по эклиптической долготе.
    ecl = ephem.Ecliptic(moon)
    ecl_lon_rad = float(ecl.lon)  # радианы
    sign_index = int(ecl_lon_rad / (math.pi / 6))  # 30° = π/6
    moon_zodiac = ZODIAC_NAMES_RU[sign_index % 12]

    return {
        'date': dt,
        'lunar_day': lunar_day,
        'phase_name': phase_name,
        'moon_zodiac': moon_zodiac,
        'illumination': round(illumination * 100, 1),
    }


def get_moon_phase_full(date_str, detailed='guest', timezone='Europe/Moscow', lat=None, lng=None):
    core = _get_lunar_core(date_str, timezone)
    dt = core['date']
    lunar_day = core['lunar_day']
    phase_name = core['phase_name']
    moon_zodiac = core['moon_zodiac']
    illumination = core['illumination']

    phase_emoji_map = {
        "Новолуние": "🌑",
        "Молодая Луна": "🌒",
        "Первая четверть": "🌓",
        "Прибывающая Луна": "🌔",
        "Полнолуние": "🌕",
        "Убывающая Луна": "🌖",
        "Последняя четверть": "🌗",
        "Старая Луна": "🌘"
    }
    phase_emoji = phase_emoji_map.get(phase_name, "🌑")

    # Восход/заход (астрологическая библиотека)
    moonrise_str = '—'
    moonset_str = '—'
    if lat is not None and lng is not None:
        try:
            from astral import moon as astral_moon
            from astral import LocationInfo
            from astral.location import Location

            info = LocationInfo('User', 'Region', 'UTC', lat, lng)
            location = Location(info)

            from datetime import date as date_type
            calc_date = date_type(dt.year, dt.month, dt.day)

            moonrise_time = astral_moon.moonrise(location.observer, calc_date)
            moonset_time = astral_moon.moonset(location.observer, calc_date)

            import pytz
            from datetime import timezone as dt_timezone

            tz = pytz.timezone(timezone)

            if moonrise_time:
                moonrise_utc = moonrise_time.replace(tzinfo=dt_timezone.utc)
                moonrise_local = moonrise_utc.astimezone(tz)
                moonrise_str = moonrise_local.strftime('%H:%M')
            else:
                moonrise_str = '—'

            if moonset_time:
                moonset_utc = moonset_time.replace(tzinfo=dt_timezone.utc)
                moonset_local = moonset_utc.astimezone(tz)
                moonset_str = moonset_local.strftime('%H:%M')
            else:
                moonset_str = '—'
        except:
            moonrise_str = '—'
            moonset_str = '—'

    # Рекомендации по лунному дню
    lunar_recommendations = {
        1: "День нового цикла. Идеально для планирования целей.",
        2: "Энергия начинает прибывать. Хорошее время для обучения.",
        3: "День активных действий. Берись за дела.",
        4: "День равновесия. Укрепляй связи.",
        5: "Творческий день. Энергия Луны поддерживает креативность.",
        6: "День интуиции. Прислушайся к внутреннему голосу.",
        7: "Магия слова. Будь осторожна с тем, что говоришь.",
        8: "День трансформации. Преодолей сомнения.",
        9: "Осторожность. Энергия нестабильна.",
        10: "День семьи и традиций.",
        11: "Энергия на пике. День рекордов и достижений.",
        12: "День любви и мудрости.",
        13: "Магический день. Подходит для ритуалов.",
        14: "Канун полнолуния. Заверши начатое.",
        15: "Полнолуние. Пик энергии. Хорошо для завершения.",
        16: "День очищения. Отпусти старые обиды.",
        17: "День радости и праздника.",
        18: "Зеркальный день. Делай выводы.",
        19: "День осторожности. Лучше отдыхать.",
        20: "День познания. Открой для себя что-то новое.",
        21: "День движения вперёд. Благоприятно для смены работы.",
        22: "День мудрости. Передавай знания.",
        23: "День очищения пространства. Заверши незаконченное.",
        24: "Пробуждение сил природы. Хорошо для контакта с землёй.",
        25: "День созерцания. Замедлись.",
        26: "День общения. Обмен идеями и планами.",
        27: "Благоприятный день для водных процедур.",
        28: "День гармонии. Хорош для красоты и ухода за собой.",
        29: "Канун новолуния. Заверши старое, прости и отпусти.",
        30: "День прощения и благодарности. Подготовься к новому циклу.",
    }
    recommendation = lunar_recommendations.get(lunar_day, "Доверься ритмам Вселенной.")

    haircut_days = {1, 2, 3, 5, 7, 10, 11, 14, 17, 20, 21, 24, 25, 28}
    haircut_recommendation = "Благоприятный день для стрижки — волосы будут расти быстро и густыми." if lunar_day in haircut_days else "Нейтральный день для стрижки — лучше выбрать другой."

    health_days = {4, 6, 8, 12, 15, 16, 18, 22, 23, 26, 27, 29}
    health_recommendation = "Благоприятный день для процедур и операций." if lunar_day not in health_days else "Лучше отложить медицинские процедуры на другой день."

    result = {
        "date": dt.strftime("%d.%m.%Y"),
        "lunar_day": lunar_day,
        "phase": f"{phase_name} {phase_emoji}",
        "illumination": illumination,
        "recommendation": recommendation,
        "phase_name": phase_name,
        "moon_zodiac": moon_zodiac,
        "moonrise": moonrise_str,
        "moonset": moonset_str,
        "haircut": haircut_recommendation,
        "health": health_recommendation,
    }

    if detailed == 'plamya':
        rituals = {
            1: "Запиши 10 желаний на новый лунный месяц.",
            15: "Зажги белую свечу и медитируй 15 минут.",
            30: "Напиши письмо-прощание со старыми обидами и сожги его.",
        }
        if lunar_day in rituals:
            result["ritual"] = rituals[lunar_day]

    return result


def get_lunar_recommendation(lunar_day, moon_zodiac):
    base = {
        1: "День нового цикла. Идеально для планирования целей на месяц. Запишите желания и визуализируйте их исполнение. Энергия чистая и податливая — используйте этот момент для закладки намерений. Всё, что вы запланируете сегодня, будет иметь особую силу в течение всего лунного месяца.",
        2: "Энергия начинает прибывать. Хорошее время для обучения и начала диеты. Организм особенно восприимчив к новой информации и полезным привычкам. Посадите семя — в прямом или переносном смысле. День благоприятен для накопления ресурсов и постепенного роста.",
        3: "День активных действий. Беритесь за дела, спорт, физическую работу. Энергия бьёт ключом — направьте её на то, что давно откладывали. Результат превзойдёт ожидания. Отличный день для старта новых проектов и решительных шагов.",
        4: "День равновесия. Укрепляйте связи, работайте с информацией. Уделите время и работе, и отдыху — в равных долях. Гармония сегодня особенно важна. Хороший день для переговоров, подписания документов и наведения порядка в делах.",
        5: "Творческий день. Энергия Луны поддерживает креативность и искусство. Рисуйте, пишите, танцуйте — всё, что выражает вашу душу. Творчество сегодня лечит. Не бойтесь экспериментировать и пробовать новое.",
        6: "День интуиции. Прислушайтесь к внутреннему голосу, медитируйте. Случайные мысли и предчувствия сегодня особенно точны. Запишите сны сразу после пробуждения — они могут содержать подсказки. Доверяйте первому впечатлению о людях.",
        7: "Магия слова. Будьте осторожны с тем, что говорите. Читайте молитвы и аффирмации — слова имеют особую силу. Одно доброе слово сегодня может изменить чью-то жизнь. Избегайте сплетен и пустых разговоров.",
        8: "День трансформации. Преодолейте сомнения. Смена имиджа, переезд, новые привычки — всё, что меняет жизнь к лучшему. Сделайте шаг, на который давно не решались. Энергия дня помогает разрушать старое и строить новое.",
        9: "Осторожность. Энергия нестабильна. Отдыхайте, избегайте стресса и конфликтов. Сегодня лучше наблюдать, чем действовать. Поберегите нервы и силы. Хороший день для спокойных дел и очищения пространства.",
        10: "День семьи и традиций. Хорошо для ремонта, домашних дел, общения с близкими. Приготовьте что-то вкусное, зажгите свечи, создайте уют. Укрепление семейных уз сегодня особенно важно.",
        11: "Энергия на пике. День рекордов и достижений. Важные сделки, переговоры, решительные шаги — всё получится. Не упустите этот мощный импульс. Единственный риск — переоценить свои силы, соблюдайте баланс.",
        12: "День любви и мудрости. Свидания, подарки, благотворительность. Маленький знак внимания сегодня принесёт большие перемены. Откройте сердце. День хорош для романтических признаний и примирения.",
        13: "Магический день. Подходит для духовных практик и ритуалов. Дверь в подсознание открыта. Зажгите благовония, помедитируйте, прислушайтесь к знакам. Сны сегодня могут быть вещими.",
        14: "Канун полнолуния. Завершите начатое, подведите промежуточные итоги. Не начинайте новое — лучше закончить старое. Подготовьтесь к пику энергии. Хороший день для генеральной уборки в доме и в мыслях.",
        15: "Полнолуние. Пик энергии, эмоции на пределе. Хорошо для завершения, но не для хирургии. Отпустите то, что тянет назад. Эмоции на пределе — будьте бережны к себе и другим. Сила дня — в освобождении.",
        16: "День очищения. Отпустите старые обиды, сделайте уборку. Избавьтесь от хлама — в доме и в мыслях. Лёгкость придёт вместе с чистотой. Хороший день для водных процедур и spa.",
        17: "День радости и праздника. Встречи, вечеринки, новые знакомства. Позвольте себе веселье и спонтанность. Смех сегодня — лучшее лекарство. День хорош для свиданий и дружеских посиделок.",
        18: "Зеркальный день. Делайте выводы, анализируйте прошлое. Какие уроки принесли последние события? Честный разговор с собой откроет новые горизонты. Не вините себя за ошибки — они были нужны для роста.",
        19: "День осторожности. Лучше отдыхать, избегать важных решений. Энергия на спаде — не насилуйте себя. Тихий вечер с книгой или фильмом восстановит силы. Избегайте больших скоплений людей.",
        20: "День познания. Откройте для себя что-то новое, учитесь. Прочитайте статью на незнакомую тему, запишитесь на курс. Знания сегодня усваиваются особенно легко. Хороший день для начала обучения.",
        21: "День движения вперёд. Благоприятно для смены работы, новых проектов и решительных шагов. Не сомневайтесь — удача на вашей стороне. Энергия дня помогает преодолевать препятствия.",
        22: "День мудрости. Передавайте знания, учите других. Ваш опыт ценен — поделитесь им. Напишите пост, дайте совет, проведите встречу. День хорош для наставничества.",
        23: "День очищения пространства. Завершите незаконченное, избавьтесь от лишнего. Разберите шкаф, балкон, рабочий стол. Вместе с вещами уходит старое. Хороший день для расхламления.",
        24: "Пробуждение сил природы. Хорошо для контакта с землёй, прогулок. Выйдите в парк, обнимите дерево, подышите свежим воздухом. Природа восстанавливает. День хорош для садоводства.",
        25: "День созерцания. Замедлитесь, ведите дневник, медитируйте. Не спешите — сегодня важно услышать себя. В тишине рождаются лучшие идеи. Посвятите время внутреннему диалогу.",
        26: "День общения. Переговоры, встречи, обмен идеями. Обсудите планы с коллегами или партнёром. Диалог сегодня приведёт к неожиданным решениям. Хороший день для мозговых штурмов.",
        27: "Благоприятный день для водных процедур, спа, ухода за собой. Вода смывает негатив и усталость. Примите ванну с солью, посетите бассейн. Энергия дня помогает расслабиться.",
        28: "День гармонии. Хорош для красоты, массажа, косметики. Побалуйте себя — новая стрижка, маска, уход. Внешняя красота отражает внутреннюю. День хорош для шопинга.",
        29: "Канун новолуния. Завершите старое, простите и отпустите. Напишите письмо обидчику и сожгите. Подготовьте чистый лист для нового цикла. День тишины и подготовки.",
        30: "День прощения и благодарности. Подготовьтесь к новому циклу. Вспомните всё хорошее за этот месяц, поблагодарите мир и себя. Зажгите свечу и помедитируйте."
    }
    zodiac_add = {
        'Овен': ' Энергия знака Овна способствует решительным действиям и новым начинаниям. Сегодня особенно хорошо начинать проекты, требующие смелости и инициативы. Не бойтесь быть первой — звёзды на вашей стороне.',
        'Телец': ' Луна в Тельце помогает укрепить материальное положение и заняться домом. Хороший день для финансовых решений, покупок для дома и заботы о теле. Наслаждайтесь простыми радостями.',
        'Близнецы': ' Энергия Близнецов усиливает общение, обучение и короткие поездки. День хорош для переговоров, писем, звонков. Обмен информацией сегодня особенно продуктивен.',
        'Рак': ' Луна в Раке обостряет чувства, внимание к семье и дому. Хороший день для домашних дел, заботы о близких и создания уюта. Эмоции могут быть сильнее обычного.',
        'Лев': ' Энергия Льва дарит уверенность, творческий подъём и радость. День хорош для публичных выступлений, самовыражения и щедрых жестов. Позвольте себе сиять.',
        'Дева': ' Луна в Деве помогает в работе, порядке, здоровье и анализах. Хороший день для наведения порядка, планирования и заботы о здоровье. Внимание к деталям сегодня окупается.',
        'Весы': ' Энергия Весов способствует гармонии, партнёрству и красоте. День хорош для переговоров, свиданий и эстетических занятий. Ищите баланс во всём.',
        'Скорпион': ' Луна в Скорпионе усиливает интуицию, трансформацию и глубокие чувства. День хорош для самоанализа, психологической работы и решения сложных вопросов. Доверьтесь внутреннему чутью.',
        'Стрелец': ' Энергия Стрельца вдохновляет на путешествия, обучение и новые горизонты. День хорош для планирования поездок, изучения нового и расширения кругозора.',
        'Козерог': ' Луна в Козероге помогает в карьере, дисциплине и долгосрочных целях. День хорош для ответственных решений, планирования карьеры и работы над репутацией.',
        'Водолей': ' Энергия Водолея усиливает оригинальность, дружбу и новые идеи. День хорош для мозговых штурмов, общения с друзьями и нестандартных решений.',
        'Рыбы': ' Луна в Рыбах обостряет эмпатию, творчество и духовность. День хорош для медитации, творчества и помощи другим. Прислушайтесь к интуиции.'
    }
    return base.get(lunar_day, "Доверьтесь ритмам Вселенной.") + zodiac_add.get(moon_zodiac, '')

def get_health_recommendation(lunar_day, moon_zodiac):
    vulnerable_organs = {
        'Овен': 'голова, мозг, глаза',
        'Телец': 'горло, шея, щитовидная железа',
        'Близнецы': 'лёгкие, бронхи, руки',
        'Рак': 'желудок, грудь, лимфатическая система',
        'Лев': 'сердце, спина, позвоночник',
        'Дева': 'кишечник, нервная система',
        'Весы': 'почки, кожа, поясница',
        'Скорпион': 'половые органы, мочевой пузырь',
        'Стрелец': 'бёдра, печень, кровь',
        'Козерог': 'кости, колени, зубы',
        'Водолей': 'голени, вены, нервная система',
        'Рыбы': 'стопы, лимфа, иммунитет',
    }
    unfavorable_surgery = {4,6,8,9,12,15,16,18,19,22,23,26,27,29}
    if lunar_day in unfavorable_surgery:
        organs = vulnerable_organs.get(moon_zodiac, 'организм')
        return f"День неблагоприятен для хирургических операций. Луна в знаке {moon_zodiac}: уязвимы {organs}. Организм ослаблен, восстановление будет медленным. Рекомендуется отдых и щадящий режим. Водные процедуры и лёгкая гимнастика помогут поддержать тонус. Отложите плановые операции минимум на сутки."
    return f"Благоприятный день для процедур и плановых операций. Организм хорошо восстанавливается. Луна в знаке {moon_zodiac}: можно уделить внимание профилактике. Хорошее время для сдачи анализов, начала курса витаминов или физиотерапии. Иммунитет активен — используйте это для укрепления здоровья."


def get_haircut_recommendation(lunar_day, moon_zodiac):
    favorable = {1,2,3,5,7,10,11,14,17,20,21,24,25,28}
    unfavorable = {9,15,19,23,29}
    if lunar_day in unfavorable:
        return "Неблагоприятный день для стрижки — волосы будут ослабленными, возможна потеря энергии. Вместе с волосами уходит жизненная сила. Также не рекомендуется окрашивание и химическая завивка. Если есть возможность — перенесите визит к парикмахеру на более удачный день."
    if lunar_day in favorable:
        return "Благоприятный день для стрижки — волосы будут расти быстрее и гуще, укрепится энергетика. Хорошо подходит для окрашивания и укладки. Новая причёска привлечёт позитивные перемены в жизнь. После стрижки рекомендуется вымыть голову тёплой водой с небольшим количеством соли — это усилит эффект."
    return "Нейтральный день. Стрижка не навредит, но и особой пользы не принесёт. Если есть сомнения — лучше отложить на благоприятный день. Можно сделать укладку или маску для волос — это безопасно."


def get_moon_month_data(year, month, detailed='brief', timezone='Europe/Moscow', mood=None, is_premium=False):
    BEST_DAYS_FOR_MOOD = {
        'finance': [2, 5, 8, 11, 14, 21, 27],
        'love': [3, 6, 12, 17, 22, 26, 28],
        'career': [1, 4, 10, 13, 18, 21, 25],
        'health': [2, 6, 9, 16, 20, 24, 28],
        'spiritual': [1, 7, 13, 19, 23, 29, 30],
    }
    MOOD_GREETINGS = {
        'finance': 'День денег и возможностей',
        'love': 'День сердца и чувств',
        'career': 'День карьеры и целей',
        'health': 'День заботы о себе',
        'spiritual': 'День души и тишины',
    }
    import calendar
    from datetime import date as date_type

    try:
        days_in_month = calendar.monthrange(year, month)[1]
        first_day = date_type(year, month, 1)
        first_day_of_week = first_day.weekday()
    except:
        return {"error": "Неверная дата"}

    rituals = {
        1: "Запишите 10 желаний на новый лунный месяц и зажгите белую свечу. Представьте, как каждое желание уже исполнилось, прочувствуйте эмоции. Сложите список и храните до следующего новолуния.",
        2: "Начните новую книгу или онлайн-курс. Посадите семя любого растения в горшок — вместе с его ростом будут расти и ваши начинания. Поливайте и ухаживайте за ним весь лунный месяц.",
        3: "Сделайте зарядку или пробежку. Энергия дня поддержит физическую активность. Включите бодрую музыку и танцуйте 10 минут — это запустит поток энергии на весь день.",
        4: "Позвоните родным. Укрепите семейные связи. Напишите тёплое сообщение тому, о ком давно не вспоминали. Слово поддержки сегодня особенно ценно.",
        5: "Займитесь творчеством: рисование, музыка, танцы, рукоделие. Не думайте о результате — важен процесс. Творчество сегодня лечит душу и открывает новые горизонты.",
        6: "Проведите 15 минут в тишине. Запишите свои сны и предчувствия в дневник. Зажгите ароматическую свечу или благовоние — аромат усилит интуицию.",
        7: "Прочитайте молитву или аффирмацию вслух. Слова имеют особую силу. Произнесите три раза: «Я выбираю свет, любовь и гармонию». Почувствуйте вибрацию голоса.",
        8: "Смените причёску или переставьте мебель. День трансформации. Сделайте то, что символизирует перемены: новое блюдо, новый маршрут на работу, новый стиль одежды.",
        9: "Примите ванну с морской солью. Очистите тело и мысли. Добавьте в воду несколько капель лавандового масла. Представьте, как вода смывает весь негатив и усталость.",
        10: "Приготовьте семейный ужин. Укрепите традиции. Зажгите свечи на столе. Пусть каждый скажет, за что он благодарен этому дню. Тепло семьи — лучшая защита.",
        11: "Сделайте важный звонок или отправьте предложение. День рекордов. Напишите письмо в будущее — себе через год. Запечатайте и откройте в следующий 11-й лунный день.",
        12: "Подарите подарок любимому человеку. Проявите заботу. Это может быть даже маленькая записка с тёплыми словами. Любовь, выраженная в действии, возвращается сторицей.",
        13: "Зажгите благовония и помедитируйте. Создайте алтарь из свечи, камня и цветка. Задайте вопрос Вселенной и будьте внимательны к знакам в течение дня.",
        14: "Завершите отложенное дело. Подведите итоги половины цикла. Напишите на бумаге всё, что хотели бы отпустить, и сожгите. Почувствуйте лёгкость.",
        15: "Зажгите три свечи и запишите достижения этого месяца. Полнолуние — время благодарности. Выйдите на балкон или во двор и посмотрите на Луну. Почувствуйте связь.",
        16: "Сделайте генеральную уборку. Выбросьте ненужные вещи. Каждая выброшенная вещь освобождает место для нового в вашей жизни. Проветрите все комнаты.",
        17: "Встретьтесь с друзьями. Устройте маленький праздник без повода. Смех и радость сегодня притягивают удачу. Поделитесь хорошим настроением с окружающими.",
        18: "Проанализируйте свои цели. Скорректируйте планы. Задайте себе вопрос: «Что я делаю не так?» и честно ответьте. Вечером запишите три вывода в дневник.",
        19: "Устройте день без соцсетей. Посвятите время себе. Почитайте книгу, примите ванну, погуляйте. Информационный детокс восстановит энергию и ясность ума.",
        20: "Прочитайте статью на новую тему. Узнайте что-то полезное. Запишите три идеи, которые пришли во время чтения. Знания — ваш главный актив в этот день.",
        21: "Составьте план на неделю. Начните новое дело. Сделайте первый, даже маленький шаг к большой цели. Движение вперёд сегодня благословлено звёздами.",
        22: "Поделитесь опытом с младшими. Напишите пост или статью. Ваши знания ценны — не держите их в себе. Одно мудрое слово может изменить чью-то жизнь.",
        23: "Разберите шкаф или рабочий стол. Избавьтесь от лишнего. Каждая ненужная вещь — это застывшая энергия. Освободите пространство для чуда.",
        24: "Выйдите на прогулку в парк. Подышите свежим воздухом. Обнимите дерево или просто прикоснитесь к нему. Природа сегодня — ваш главный целитель.",
        25: "Ведите дневник благодарности. Запишите 5 вещей, за которые вы благодарны этому дню. Замедлитесь, выпейте чай в тишине, послушайте спокойную музыку.",
        26: "Проведите встречу или созвон с коллегами. Обменяйтесь идеями. Одна случайная мысль в разговоре может стать началом большого проекта.",
        27: "Посетите спа или сделайте маску для лица дома. Вода сегодня смывает не только усталость, но и тревоги. Добавьте в ванну лепестки роз или эфирное масло.",
        28: "Сделайте массаж или самомассаж. День ухода за телом. Нанесите любимый крем, сделайте маску для волос. Внешняя красота сегодня питает внутреннюю.",
        29: "Напишите письмо обидчику и сожгите его. Отпустите прошлое. Прощение — это подарок не другому, а себе. Почувствуйте, как груз падает с плеч.",
        30: "Поблагодарите мир за всё хорошее в этом лунном месяце. Подготовьте список целей на новый цикл. Зажгите свечу и посидите в тишине, вспоминая лучшие моменты.",
    }

    days = []
    for day_num in range(1, days_in_month + 1):
        date_str = f"{year:04d}-{month:02d}-{day_num:02d}"
        try:
            core = _get_lunar_core(date_str, timezone)
            lunar_day = core['lunar_day']
            phase_name = core['phase_name']
            moon_zodiac = core['moon_zodiac']
            illumination = core['illumination']
        except:
            lunar_day, phase_name, moon_zodiac, illumination = 0, "—", "—", 0

        recommendation = get_lunar_recommendation(lunar_day, moon_zodiac)
        haircut = get_haircut_recommendation(lunar_day, moon_zodiac)
        health = get_health_recommendation(lunar_day, moon_zodiac)

        if detailed == 'guest':
            day_entry = {
                "day": day_num,
                "date": date_str,
                "lunar_day": lunar_day,
                "phase_name": phase_name,
                "illumination": illumination,
                "moon_zodiac": moon_zodiac,
                "recommendation": recommendation,
                "haircut": "",
                "health": "",
            }
        else:
            day_entry = {
                "day": day_num,
                "date": date_str,
                "lunar_day": lunar_day,
                "phase_name": phase_name,
                "illumination": illumination,
                "moon_zodiac": moon_zodiac,
                "recommendation": recommendation,
                "haircut": haircut,
                "health": health,
            }
            if is_premium and lunar_day in rituals:
                day_entry["ritual"] = rituals[lunar_day]
            
            # Обрезаем рекомендацию для бесплатных
            if not is_premium:
                _teasers = [
                    'Полный разбор дня откроет конкретные шаги.',
                    'Детали этого дня могут изменить планы — узнайте как.',
                    'Один неожиданный совет способен перевернуть этот день.',
                    'Что звёзды приготовили лично для вас?',
                    'Энергия дня таит подсказку, которую стоит расшифровать.'
                ]
                full_rec = day_entry.get('recommendation', '')
                if full_rec:
                    sentences = full_rec.split('. ')
                    day_entry['recommendation'] = '. '.join(sentences[:2]) + '. ' + _random.choice(_teasers)

        days.append(day_entry)

    result = {
        "year": year,
        "month": month,
        "days_in_month": days_in_month,
        "first_day_of_week": first_day_of_week,
        "days": days,
    }

    if mood and mood in BEST_DAYS_FOR_MOOD:
        result["highlighted_days"] = BEST_DAYS_FOR_MOOD[mood]
        result["mood"] = mood
        result["mood_greeting"] = MOOD_GREETINGS.get(mood, "")

    return result


def get_moon_day_ai_recommendation(year, month, day, timezone='Europe/Moscow', user_tags=None, user_name="", user_zodiac="", subscription="Искра", user_id=None):
    date_str = f"{year:04d}-{month:02d}-{day:02d}"
    try:
        core = _get_lunar_core(date_str, timezone)
        lunar_day = core['lunar_day']
        phase_name = core['phase_name']
        moon_zodiac = core['moon_zodiac']
        illumination = core['illumination']
        dt = core['date']
    except:
        return None

    tags_text = ", ".join(set(user_tags)) if user_tags else "не указаны"
    name_line = f"Имя: {user_name}. " if user_name else ""
    zodiac_line = f"Знак зодиака: {user_zodiac}. " if user_zodiac else ""
    day_of_week = dt.strftime('%A')
    from utils.helpers import now_msk as _now_msk
    hour = _now_msk().hour
    time_context = "утро" if hour < 12 else ("день" if hour < 18 else "вечер")

    ai_text = ask_deepseek(
        system_prompt=f"""Ты - личный астролог и доверительная подруга. Твой тон - тёплый, заботливый, без пафоса и нравоучений.

Сегодня {lunar_day}-й лунный день, {day_of_week}, {time_context}. Луна в знаке {moon_zodiac}, фаза: {phase_name}. Освещённость: {illumination}%.
{name_line}{zodiac_line}Интересы: {tags_text}.

Напиши персональный путеводитель на день.

СТРУКТУРА ОТВЕТА (строго соблюдай):
1. Первая строка - заголовок (3-5 слов, тёплый, женственный, без эмодзи).
2. Пустая строка.
3. Абзац "Энергия дня" - 2 предложения о том, как лунный день и знак Луны влияют на настроение и поступки.
4. Абзац "Совет" - 2-3 предложения: конкретное действие, связанное с интересами. Учитывай время суток ({time_context}).
5. Абзац "Аффирмация дня" - одно предложение в кавычках.
6. Абзац "Шёпот звёзд" - одно неожиданное, немного провокационное наблюдение или вопрос, который заставит задуматься. Не банальное.

ПРАВИЛА:
- Без эмодзи в заголовке и тексте.
- Без обращений "ты", "вы". Пиши безлично: "сегодня благоприятно...", "энергия дня поддерживает...", "звёзды шепчут...".
- Не повторяй статические рекомендации (благоприятные дела, стрижки, здоровье). Это должно быть новое, более глубокое.
- В "Шёпоте звёзд" - удиви, заинтригуй. Иногда это может быть немного дерзким или неожиданным.
- Тон - как у мудрой подруги за чашкой чая: тепло, но без слащавости.
- { "Длина: 5-7 предложений всего." if subscription == "Искра" else "Длина: 7-9 предложений всего. Раскрой мысли глубже." }""",
        user_prompt=f"День: {lunar_day}-й лунный. Луна в {moon_zodiac}. Фаза: {phase_name}. {name_line}Интересы: {tags_text}. Время суток: {time_context}. Дай персональный путеводитель.",
        temperature=0.85,
        user_id=user_id
    )
    return ai_text


def get_personal_categories(lunar_day, moon_zodiac, dominant_tag=None, user_tags=None):
    categories = []
    
    lunar_map = {
        1: [{"title": "🌱 Намерение дня", "desc": "Запишите одно главное желание на этот лунный месяц. Энергия новолуния усилит его исполнение."}],
        2: [{"title": "📚 Чему научиться", "desc": "День благоприятен для усвоения новой информации. Выделите 20 минут на обучение."}],
        3: [{"title": "⚡ Точка силы", "desc": "Самый активный день цикла. Направьте энергию на то, что давно откладывали."}],
        4: [{"title": "🧘 Внутренний баланс", "desc": "День равновесия. Уделите время и работе, и отдыху — в равных долях."}],
        5: [{"title": "🎨 Творческий импульс", "desc": "Займитесь тем, что приносит радость: рисование, музыка, танцы. Творчество сегодня лечит."}],
        6: [{"title": "🔮 Знак судьбы", "desc": "Обратите внимание на случайные встречи и совпадения — они не случайны."}],
        7: [{"title": "🗣 Сила голоса", "desc": "Слова сегодня имеют особую силу. Произнесите аффирмацию вслух."}],
        8: [{"title": "🦋 Трансформация", "desc": "День перемен. Смените причёску, переставьте мебель, попробуйте новое."}],
        9: [{"title": "🛡 Защита энергии", "desc": "Избегайте конфликтов и негативных людей. Ваше поле уязвимо."}],
        10: [{"title": "🏡 Уют и корни", "desc": "Проведите вечер с близкими. Приготовьте что-то вкусное, зажгите свечи."}],
        11: [{"title": "🚀 Прорыв", "desc": "День рекордов. Сделайте то, на что давно не решались. Энергия на пике."}],
        12: [{"title": "💝 Дар любви", "desc": "Подарите подарок тому, кого любите. Маленький знак внимания принесёт большие перемены."}],
        13: [{"title": "🌙 Магия дня", "desc": "Зажгите благовония, помедитируйте. Дверь в подсознание открыта."}],
        14: [{"title": "📋 Подведение итогов", "desc": "Завершите начатое до полнолуния. Подведите промежуточные итоги."}],
        15: [{"title": "🌕 Пик силы", "desc": "Полнолуние — время завершения. Отпустите то, что тянет назад."}],
        16: [{"title": "🧹 Очищение", "desc": "Сделайте генеральную уборку — в доме и в мыслях. Выбросьте ненужное."}],
        17: [{"title": "🎉 Маленький праздник", "desc": "Встретьтесь с друзьями или устройте свидание с собой. День радости."}],
        18: [{"title": "🪞 Зеркало души", "desc": "Проанализируйте последние события. Какие уроки они принесли?"}],
        19: [{"title": "🌊 Пауза", "desc": "День тишины. Отдохните, выспитесь, не принимайте важных решений."}],
        20: [{"title": "📖 Открытие", "desc": "Узнайте что-то новое. Прочитайте статью, посмотрите лекцию, запишитесь на курс."}],
        21: [{"title": "🏃 Движение вперёд", "desc": "Благоприятный день для смены работы, новых проектов и решительных шагов."}],
        22: [{"title": "🎓 Наставничество", "desc": "Поделитесь опытом с младшими. Напишите пост, дайте совет — это вернётся."}],
        23: [{"title": "🗑 Избавление", "desc": "Разберите шкаф, балкон, рабочий стол. Вместе с вещами уходит старое."}],
        24: [{"title": "🌿 Природа", "desc": "Выйдите на прогулку. Контакт с землёй и деревьями восстанавливает силы."}],
        25: [{"title": "📓 Дневник", "desc": "Запишите мысли и чувства. Ведение дневника сегодня особенно целительно."}],
        26: [{"title": "🤝 Диалог", "desc": "День переговоров. Обсудите планы с коллегами или партнёром."}],
        27: [{"title": "💧 Водная магия", "desc": "Примите ванну с солью, посетите спа. Вода смывает негатив."}],
        28: [{"title": "💄 Красота", "desc": "День ухода за собой. Массаж, маска, новая косметика — всё к лучшему."}],
        29: [{"title": "🕊 Прощение", "desc": "Напишите письмо обидчику и сожгите. Отпустите прошлое с благодарностью."}],
        30: [{"title": "🙏 Благодарность", "desc": "Вспомните всё хорошее за этот лунный месяц. Поблагодарите мир."}],
    }
    
    if lunar_day in lunar_map:
        categories.extend(lunar_map[lunar_day])
    
    if dominant_tag:
        tag_categories = {
            'love': [
                {"title": "💕 Совет сердцу", "desc": "Сегодня важно услышать не только себя, но и партнёра. Задайте вопрос и внимательно выслушайте ответ."},
                {"title": "💌 Знак от Вселенной", "desc": "Обратите внимание на повторяющиеся цифры или имена — это подсказка в личной жизни."},
            ],
            'career': [
                {"title": "📈 Карьерный шаг", "desc": "Запишите 3 цели на этот лунный месяц. Конкретные, измеримые, с дедлайном."},
                {"title": "🤝 Нужный человек", "desc": "Сегодня вероятна встреча, которая повлияет на карьеру. Будьте открыты к знакомствам."},
            ],
            'finance': [
                {"title": "💰 Денежный поток", "desc": "Запишите все траты за день. Осознанность в финансах — первый шаг к изобилию."},
                {"title": "💎 Ваш ресурс", "desc": "Подумайте: какой навык приносит вам больше всего денег? Как его усилить?"},
            ],
            'health': [
                {"title": "🧘 Тело и дух", "desc": "Выделите 15 минут на растяжку или дыхательные упражнения. Тело скажет спасибо."},
                {"title": "🥗 Энергия дня", "desc": "Обратите внимание на питание. Лёгкая пища сегодня принесёт больше энергии."},
            ],
            'spiritual': [
                {"title": "🌌 Послание свыше", "desc": "Запишите сон или предчувствие. Интуиция сегодня особенно сильна."},
                {"title": "🕯 Минута тишины", "desc": "Посидите в тишине 10 минут. Ответ, который вы ищете, уже внутри."},
            ],
            'sad': [
                {"title": "🌧 Утешение", "desc": "Даже в пасмурный день есть свет. Позвольте себе отдохнуть — завтра будет легче."},
                {"title": "☕ Маленькая радость", "desc": "Сделайте себе подарок: чашка любимого чая, фильм, тёплый плед. Вы заслуживаете заботы."},
            ],
        }
        
        if dominant_tag in tag_categories:
            categories.extend(tag_categories[dominant_tag])
    
    return categories[:4]


def get_moon_phase_for_panel(date_str, timezone='Europe/Moscow', is_premium=False):
    core = _get_lunar_core(date_str, timezone)
    lunar_day = core['lunar_day']
    phase_name = core['phase_name']
    moon_zodiac = core['moon_zodiac']

    recommendation = get_lunar_recommendation(lunar_day, moon_zodiac)
    haircut = get_haircut_recommendation(lunar_day, moon_zodiac)
    health = get_health_recommendation(lunar_day, moon_zodiac)

    favorable_map = {
        1: 'Планирование и визуализация целей на месяц. Составление карты желаний — энергия новолуния усилит каждое записанное намерение. Медитация на новый цикл, зажжение свечи как символа начала. День хорош для закладки фундамента: первые шаги в новых проектах, запуск бизнес-идей, формулировка целей.',
        2: 'Обучение и усвоение новой информации — мозг сегодня особенно восприимчив. Начало диеты или нового режима питания — организм настроен на принятие. Планирование покупок, особенно крупных — интуиция подскажет верное решение. Знакомства для обмена идеями и опытом.',
        3: 'Активные физические действия: спорт, тренировки, физическая работа. Решение сложных задач, которые давно откладывались — энергия дня помогает пробить застои. Начало новых проектов, запуск бизнес-процессов. День хорош для соревнований и принятия вызовов.',
        4: 'Укрепление отношений с близкими и коллегами через искренний диалог. Работа с документами, подписание договоров, наведение порядка в бумагах и файлах. Планирование бюджета, финансовый учёт. День хорош для создания уюта в доме — перестановка, декор.',
        5: 'Творчество во всех проявлениях: рисование, музыка, танцы, рукоделие, писательство. Всё, что приносит радость и позволяет выразить душу. Посещение выставок, концертов, творческих встреч. Свидание или романтический вечер — энергия дня усиливает чувства.',
        6: 'Медитация и работа с интуицией — внутренний голос сегодня особенно точен. Запись снов сразу после пробуждения — они содержат подсказки. Анализ предчувствий и первых впечатлений о людях — они редко ошибаются. День хорош для уединения и самоанализа.',
        7: 'Произнесение молитв и аффирмаций вслух — слова имеют особую силу. Публичные выступления, презентации, переговоры. Поэзия, пение, работа с голосом. День хорош для важных заявлений и признаний — сказанное сегодня запомнится надолго.',
        8: 'Смена имиджа, стрижка, окрашивание — перемены во внешности приведут к внутренним сдвигам. Переезд или перестановка мебели. Внедрение новых привычек, отказ от вредных. День хорош для смелых решений, которые давно откладывались.',
        9: 'Отдых и восстановление — тело и разум требуют паузы. Очищение пространства: разбор шкафов, балкона, рабочего стола. Водные процедуры, ванна с морской солью. Тишина и минимум контактов — день для себя.',
        10: 'Семейные дела и общение с близкими. Ремонт, обустройство дома, приготовление еды. Укрепление традиций — семейный ужин, настольные игры, разговоры по душам. День хорош для покупок для дома и создания уюта.',
        11: 'Важные проекты, сделки, переговоры — энергия на пике, всё получается. Публичные выступления и презентации. День рекордов: сделать то, на что давно не решались. Старт новых бизнес-направлений.',
        12: 'Свидания и романтические встречи. Подарки близким, благотворительность, помощь нуждающимся. Признания в чувствах, предложения руки и сердца. День хорош для примирения и восстановления отношений.',
        13: 'Духовные практики, медитация, работа с подсознанием. Зажжение благовоний, создание алтаря. Ритуалы на привлечение желаемого. Сны сегодня могут быть вещими — записывайте. День хорош для обращения к наставникам и духовным учителям.',
        14: 'Завершение проектов и подведение промежуточных итогов. Уборка рабочего места, расхламление. Подготовка к полнолунию: завершить начатое, не начинать новое. Анализ достижений за половину цикла.',
        15: 'Завершение дел и проектов — полнолуние ставит точку. Празднование достижений, благодарность себе и миру. Отпускание старого: написать список того, что тянет назад, и сжечь. Медитация при свечах. Не начинать новое.',
        16: 'Генеральная уборка в доме и в мыслях. Избавление от хлама и старых вещей — каждая выброшенная вещь освобождает место для нового. Проветривание помещений. Водные процедуры и spa.',
        17: 'Встречи с друзьями, вечеринки, праздники без повода. Новые знакомства — люди, встреченные сегодня, могут сыграть важную роль. Смех и радость притягивают удачу. День хорош для свиданий и лёгкого флирта.',
        18: 'Анализ последних событий: какие уроки они принесли. Планирование будущего с учётом полученного опыта. Работа над ошибками. Честный разговор с собой — записать три вывода в дневник.',
        19: 'Полный отдых и релаксация. Чтение, просмотр фильмов, тишина. Никаких важных решений и переговоров. Энергия на спаде — поберегите силы. Ванна с лавандой, тёплый плед, любимая музыка.',
        20: 'Учёба и освоение новых навыков. Чтение книг, статей, просмотр лекций. Запись на курс или вебинар. Знания сегодня усваиваются легко и надолго. День хорош для начала обучения.',
        21: 'Смена работы или должности. Запуск новых проектов. Смелые шаги в карьере. Составление плана на неделю. Движение вперёд сегодня благословлено звёздами — не сомневайтесь.',
        22: 'Наставничество и передача опыта. Обучение других, написание статей и постов. Ваш опыт ценен — поделитесь им. День хорош для проведения мастер-классов и вебинаров.',
        23: 'Расхламление и избавление от лишнего. Разбор шкафов, балкона, рабочего стола. Вместе с вещами уходит старое. Освободите пространство для чуда. Не начинать новое — только завершать.',
        24: 'Прогулки на природе, контакт с землёй и деревьями. Садоводство, пикники, отдых на свежем воздухе. Природа сегодня восстанавливает силы лучше любого лекарства. День хорош для физической активности.',
        25: 'Ведение дневника: запись мыслей и чувств. Медитация и самоанализ. Замедление — не спешите, сегодня важно услышать себя. Посвятите время внутреннему диалогу. Никаких шумных компаний.',
        26: 'Переговоры и деловые встречи — диалог сегодня приводит к неожиданным решениям. Мозговые штурмы и обмен идеями. Командная работа особенно продуктивна. Планирование совместных проектов. Общение с коллегами и партнёрами.',
        27: 'Водные процедуры: ванна с солью, бассейн, спа. Вода смывает негатив и усталость. Уход за телом: маски, обёртывания. День хорош для расслабления и восстановления после нагрузок.',
        28: 'Уход за внешностью: массаж, стрижка, маски, новая косметика. Шопинг и обновление гардероба. Внешняя красота сегодня питает внутреннюю. День хорош для салонных процедур.',
        29: 'Завершение старых дел и отношений. Прощение обид — написать письмо обидчику и сжечь. Подготовка к новому циклу. День тишины и внутренней работы. Не начинать новое.',
        30: 'Благотворительность и помощь другим. Подведение итогов лунного месяца. Благодарность миру и себе за пройденный путь. Подготовка списка целей на новый цикл. Зажжение свечи и медитация.',
    }
    unfavorable_map = {
        1: 'Новые проекты запускать рано — энергия ещё не набрала силу. Активные действия и важные переговоры лучше отложить на 2-3 дня. Импульсивные решения, особенно финансовые, могут привести к потерям. Конфликты и выяснение отношений сегодня особенно разрушительны.',
        2: 'Конфликты и споры с близкими — энергия дня делает людей ранимыми, любое резкое слово оставит глубокий след. Выяснение отношений и жёсткая критика приведут к затяжным ссорам. Не начинайте диету с голодания — организм не готов к экстриму.',
        3: 'Пассивность и лень в этот день особенно вредны — энергия требует выхода, иначе она превратится в раздражительность. Откладывание важных дел приведёт к накоплению проблем. Игнорирование физической активности вызовет застой энергии и плохое настроение.',
        4: 'Одиночество и изоляция сегодня противопоказаны — день требует обмена энергией с другими людьми. Отказ от помощи из гордыни закроет возможности. Работа в одиночку над командными проектами приведёт к ошибкам.',
        5: 'Рутина и однообразная работа убьют творческий импульс дня. Скука и подавление творческих порывов приведут к эмоциональному спаду. Не заставляйте себя делать то, что не приносит радости — найдите альтернативу.',
        6: 'Игнорирование интуиции и внутреннего голоса — сегодня они точны как никогда. Излишняя рациональность и попытки всё объяснить логикой заведут в тупик. Споры с предчувствиями приведут к ошибочным решениям.',
        7: 'Сплетни и пустые разговоры сегодня имеют разрушительную силу — слова ранят глубже обычного. Критика и осуждение других вернутся бумерангом. Ложь, даже невинная, раскроется в самый неподходящий момент.',
        8: 'Рискованные операции и экстремальные виды спорта — день травмоопасен. Конфликты с руководством и авторитетными фигурами приведут к долгосрочным проблемам. Резкая смена имиджа без подготовки может разочаровать.',
        9: 'Стресс и перегрузки сегодня особенно опасны — нервная система на пределе. Важные решения, принятые в этот день, скорее всего будут ошибочными. Тяжёлая пища и алкоголь ударят по здоровью сильнее обычного.',
        10: 'Ссоры с близкими и критика родных — раны, нанесённые сегодня, заживают долго. Изоляция от семьи в день, когда энергия требует единения, приведёт к чувству опустошённости. Откладывание домашних дел на потом.',
        11: 'Переутомление и работа на износ — энергия на пике, но ресурсы не бесконечны. Игнорирование отдыха приведёт к выгоранию. Чрезмерные амбиции и попытки сделать всё сразу закончатся провалом.',
        12: 'Выяснение отношений с партнёром — день слишком эмоционально заряжен, любое неосторожное слово приведёт к ссоре. Ревность и упрёки разрушат даже крепкие отношения. Отказ в помощи тем, кто просит.',
        13: 'Тяжёлая пища и алкоголь — организм сегодня особенно чувствителен к токсинам. Шумные вечеринки и пустые развлечения опустошат энергетически. Игнорирование духовных практик и знаков судьбы.',
        14: 'Новые начинания и старт проектов — канун полнолуния не время для стартов. Важные покупки и инвестиции могут оказаться невыгодными. Активные действия лучше отложить до следующего лунного дня.',
        15: 'Хирургические операции — полнолуние даёт высокий риск кровотечений. Стресс и конфликты — эмоции на пределе, любое столкновение перерастёт в крупную ссору. Излишняя эмоциональность в принятии решений.',
        16: 'Новые знакомства и важные переговоры — день очищения не для этого. Крупные покупки — вероятность приобрести ненужное. Начало новых проектов — энергия идёт на спад.',
        17: 'Работа в одиночку и уединение — день требует общения и обмена энергией. Отказ от приглашений и встреч с друзьями. Серьёзные разговоры и выяснение отношений.',
        18: 'Импульсивные решения и спонтанные покупки — не поддавайтесь эмоциям. Резкие перемены без анализа последствий. Крупные финансовые операции — отложите на день.',
        19: 'Важные переговоры и подписание контрактов — внимание рассеяно, легко пропустить детали. Новые обязательства и обещания — не удастся сдержать. Активные действия — энергия на нуле.',
        20: 'Спешка и суета — знания не усваиваются в спешке. Многозадачность и распыление внимания. Отказ от обучения и новых знаний — упустите благоприятный момент.',
        21: 'Пассивность и лень в день, когда энергия толкает вперёд — упустите возможности. Откладывание важных решений на потом. Игнорирование карьерных шансов.',
        22: 'Эгоизм и гордыня — отказ слушать других и навязывание своего мнения. Отказ делиться опытом и помогать младшим. Замкнутость и изоляция от коллектива.',
        23: 'Хирургические операции и косметические процедуры — высокий риск осложнений. Стрижка в этот день ослабляет волосы. Новые начинания — день только для завершения.',
        24: 'Затворничество и избегание прогулок — природа сегодня лечит, не отказывайте себе в этом. Отказ от физической активности. Игнорирование сигналов тела.',
        25: 'Шумные компании и перегрузка общением — день требует тишины. Игнорирование интуиции и внутреннего голоса. Отказ от ведения дневника и самоанализа.',
        26: 'Споры и конфликты — жёсткие переговоры и ультиматумы приведут к разрыву отношений. Отказ от диалога и обмена идеями. Замкнутость и нежелание слышать других.',
        27: 'Переохлаждение и сквозняки — риск простудных заболеваний повышен. Купание в холодной воде. Отказ от водных процедур и ухода за телом.',
        28: 'Хирургические операции и инъекции — отложите на другой день. Агрессивные косметические процедуры и пилинги. Конфликты и нарушение гармонии.',
        29: 'Новые начинания и старты — канун новолуния не время для этого. Важные знакомства и переговоры. Крупные покупки и инвестиции.',
        30: 'Уныние и грусть — не застревайте в прошлом. Самокритика и сожаления. Отказ от благодарности и подведения итогов.',
    }

    rituals = {
        1: "Запишите 10 желаний на новый лунный месяц и зажгите белую свечу. Представьте, как каждое желание уже исполнилось, прочувствуйте эмоции. Сложите список и храните до следующего новолуния.",
        2: "Начните новую книгу или онлайн-курс. Посадите семя любого растения в горшок — вместе с его ростом будут расти и ваши начинания. Поливайте и ухаживайте за ним весь лунный месяц.",
        3: "Сделайте зарядку или пробежку. Энергия дня поддержит физическую активность. Включите бодрую музыку и танцуйте 10 минут — это запустит поток энергии на весь день.",
        4: "Позвоните родным. Укрепите семейные связи. Напишите тёплое сообщение тому, о ком давно не вспоминали. Слово поддержки сегодня особенно ценно.",
        5: "Займитесь творчеством: рисование, музыка, танцы, рукоделие. Не думайте о результате — важен процесс. Творчество сегодня лечит душу и открывает новые горизонты.",
        6: "Проведите 15 минут в тишине. Запишите свои сны и предчувствия в дневник. Зажгите ароматическую свечу или благовоние — аромат усилит интуицию.",
        7: "Прочитайте молитву или аффирмацию вслух. Слова имеют особую силу. Произнесите три раза: «Я выбираю свет, любовь и гармонию». Почувствуйте вибрацию голоса.",
        8: "Смените причёску или переставьте мебель. День трансформации. Сделайте то, что символизирует перемены: новое блюдо, новый маршрут на работу, новый стиль одежды.",
        9: "Примите ванну с морской солью. Очистите тело и мысли. Добавьте в воду несколько капель лавандового масла. Представьте, как вода смывает весь негатив и усталость.",
        10: "Приготовьте семейный ужин. Укрепите традиции. Зажгите свечи на столе. Пусть каждый скажет, за что он благодарен этому дню. Тепло семьи — лучшая защита.",
        11: "Сделайте важный звонок или отправьте предложение. День рекордов. Напишите письмо в будущее — себе через год. Запечатайте и откройте в следующий 11-й лунный день.",
        12: "Подарите подарок любимому человеку. Проявите заботу. Это может быть даже маленькая записка с тёплыми словами. Любовь, выраженная в действии, возвращается сторицей.",
        13: "Зажгите благовония и помедитируйте. Создайте алтарь из свечи, камня и цветка. Задайте вопрос Вселенной и будьте внимательны к знакам в течение дня.",
        14: "Завершите отложенное дело. Подведите итоги половины цикла. Напишите на бумаге всё, что хотели бы отпустить, и сожгите. Почувствуйте лёгкость.",
        15: "Зажгите три свечи и запишите достижения этого месяца. Полнолуние — время благодарности. Выйдите на балкон или во двор и посмотрите на Луну. Почувствуйте связь.",
        16: "Сделайте генеральную уборку. Выбросьте ненужные вещи. Каждая выброшенная вещь освобождает место для нового в вашей жизни. Проветрите все комнаты.",
        17: "Встретьтесь с друзьями. Устройте маленький праздник без повода. Смех и радость сегодня притягивают удачу. Поделитесь хорошим настроением с окружающими.",
        18: "Проанализируйте свои цели. Скорректируйте планы. Задайте себе вопрос: «Что я делаю не так?» и честно ответьте. Вечером запишите три вывода в дневник.",
        19: "Устройте день без соцсетей. Посвятите время себе. Почитайте книгу, примите ванну, погуляйте. Информационный детокс восстановит энергию и ясность ума.",
        20: "Прочитайте статью на новую тему. Узнайте что-то полезное. Запишите три идеи, которые пришли во время чтения. Знания — ваш главный актив в этот день.",
        21: "Составьте план на неделю. Начните новое дело. Сделайте первый, даже маленький шаг к большой цели. Движение вперёд сегодня благословлено звёздами.",
        22: "Поделитесь опытом с младшими. Напишите пост или статью. Ваши знания ценны — не держите их в себе. Одно мудрое слово может изменить чью-то жизнь.",
        23: "Разберите шкаф или рабочий стол. Избавьтесь от лишнего. Каждая ненужная вещь — это застывшая энергия. Освободите пространство для чуда.",
        24: "Выйдите на прогулку в парк. Подышите свежим воздухом. Обнимите дерево или просто прикоснитесь к нему. Природа сегодня — ваш главный целитель.",
        25: "Ведите дневник благодарности. Запишите 5 вещей, за которые вы благодарны этому дню. Замедлитесь, выпейте чай в тишине, послушайте спокойную музыку.",
        26: "Проведите встречу или созвон с коллегами. Обменяйтесь идеями. Одна случайная мысль в разговоре может стать началом большого проекта.",
        27: "Посетите спа или сделайте маску для лица дома. Вода сегодня смывает не только усталость, но и тревоги. Добавьте в ванну лепестки роз или эфирное масло.",
        28: "Сделайте массаж или самомассаж. День ухода за телом. Нанесите любимый крем, сделайте маску для волос. Внешняя красота сегодня питает внутреннюю.",
        29: "Напишите письмо обидчику и сожгите его. Отпустите прошлое. Прощение — это подарок не другому, а себе. Почувствуйте, как груз падает с плеч.",
        30: "Поблагодарите мир за всё хорошее в этом лунном месяце. Подготовьте список целей на новый цикл. Зажгите свечу и посидите в тишине, вспоминая лучшие моменты.",
    }

    result = {
        "lunar_day": lunar_day,
        "phase_name": phase_name,
        "moon_zodiac": moon_zodiac,
        "recommendation": recommendation,
        "favorable": favorable_map.get(lunar_day, ''),
        "unfavorable": unfavorable_map.get(lunar_day, ''),
        "haircut": haircut,
        "health": health,
    }

    if is_premium and lunar_day in rituals:
        result["ritual"] = rituals[lunar_day]

    if not is_premium:
        teasers = [
            'Полный разбор дня откроет конкретные шаги.',
            'Детали этого дня могут изменить планы — узнайте как.',
            'Один неожиданный совет способен перевернуть этот день.',
            'Что звёзды приготовили лично для вас?',
            'Энергия дня таит подсказку, которую стоит расшифровать.'
        ]
        full_rec = result.get('recommendation', '')
        if full_rec:
            sentences = full_rec.split('. ')
            result['recommendation'] = '. '.join(sentences[:2]) + '. ' + _random.choice(teasers)
        for key in ['favorable', 'unfavorable', 'haircut', 'health']:
            if key in result and result[key]:
                sentences = result[key].split('. ')
                result[key] = '. '.join(sentences[:1]) + '. ' + _random.choice(teasers)

    return result