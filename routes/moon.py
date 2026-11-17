# routes/moon.py
from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user
import json

from utils.helpers import get_user_access_level, get_zodiac_sign, today_msk, now_msk
from utils.orchestrator import get_or_create_portrait
from utils.ai_service import ai_moon_day_full
from utils.extensions import limiter

from database.db import get_db
from utils.calculators import (
    get_moon_phase_full,
    get_moon_month_data,
    get_moon_day_ai_recommendation,
    get_moon_phase_for_panel
)
from utils.ai_service import ask_deepseek, ai_moon_suggestions
from utils.auth_core import csrf_required
from utils.helpers import get_identifier, get_location_by_ip

moon_bp = Blueprint('moon', __name__)

# ---------- Страница ----------
@moon_bp.route('/moon-calendar')
def moon_calendar_page():
    return render_template('moon_calendar.html')

# ---------- Полная информация о дне ----------
@moon_bp.route('/api/moon-calendar/full', methods=['POST'])
@csrf_required
@limiter.limit("20 per minute;200 per hour")
def api_moon_calendar_full():
    data = request.json or {}
    date_str = data.get('date', '')
    timezone = data.get('timezone', 'Europe/Moscow')
    lat, lng = get_location_by_ip(request.remote_addr)
    detailed = get_user_access_level()
    result = get_moon_phase_full(date_str, detailed=detailed, timezone=timezone, lat=lat, lng=lng)
    return jsonify(result)

# ---------- Данные на месяц ----------
@moon_bp.route('/api/moon-calendar/month', methods=['POST'])
@csrf_required
@limiter.limit("20 per minute;200 per hour")
def api_moon_calendar_month():
    data = request.json or {}
    _now = now_msk()
    year = data.get('year', _now.year)
    month = data.get('month', _now.month)
    timezone_str = data.get('timezone', 'Europe/Moscow')
    mood = data.get('mood', None)

    detailed = get_user_access_level()
    if detailed == 'brief' and not current_user.is_authenticated:
        detailed = 'guest'

    is_premium = current_user.is_authenticated and current_user.subscription == 'Пламя'
    result = get_moon_month_data(year, month, detailed=detailed, timezone=timezone_str, mood=mood, is_premium=is_premium)
    return jsonify(result)

# ---------- AI-рекомендация дня ----------
@moon_bp.route('/api/moon-calendar/day-ai', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;50 per hour")
def api_moon_day_ai_recommendation():
    if not current_user.is_authenticated or current_user.subscription != 'Пламя':
        return jsonify({"error": "Доступно на тарифе Пламя"}), 402

    data = request.json or {}
    year = data.get('year')
    month = data.get('month')
    day = data.get('day')
    timezone_str = data.get('timezone', 'Europe/Moscow')

    if not all([year, month, day]):
        return jsonify({"error": "Неверные параметры"}), 400

    identifier = get_identifier()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT tags_json FROM daily_insights WHERE user_id = ?",
            (identifier,)
        ).fetchall()

    user_tags = []
    for row in rows:
        row_tags = json.loads(row['tags_json'])
        user_tags.extend(row_tags)

    user_name = ""
    user_zodiac = ""
    if current_user.is_authenticated:
        user_name = current_user.name or ""
        birth_date = current_user.birth_date or ""
        if birth_date:
            user_zodiac = get_zodiac_sign(birth_date) or ""

    subscription = current_user.subscription if current_user.is_authenticated else 'Искра'

    ai_text = get_moon_day_ai_recommendation(
        year, month, day, timezone_str, user_tags,
        user_name=user_name, user_zodiac=user_zodiac,
        subscription=subscription,
        user_id=identifier
    )
    return jsonify({"ai_recommendation": ai_text})

# ---------- Вопрос по лунному дню ----------
@moon_bp.route('/api/moon-calendar/ask', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;50 per hour")
def api_moon_ask():
    if not current_user.is_authenticated or current_user.subscription != 'Пламя':
        return jsonify({"error": "Доступно на тарифе Пламя"}), 402

    data = request.json or {}
    question = data.get('question', '').strip()
    lunar_day = data.get('lunar_day')
    phase_name = data.get('phase_name')
    moon_zodiac = data.get('moon_zodiac')

    if not question:
        return jsonify({"error": "Напишите вопрос"}), 400
    if len(question) > 500:
        return jsonify({"error": "Вопрос слишком длинный (макс. 500 символов)"}), 400

    today = today_msk()

    ai_answer = ask_deepseek(
        system_prompt=f"""Ты — астролог и эксперт по лунному календарю. 
    Сегодня {lunar_day}-й лунный день, фаза: {phase_name}, Луна в знаке {moon_zodiac}.
    Ответь на вопрос, учитывая энергию этого лунного дня и знака Луны.
    3-5 предложений. Тёплый, заботливый тон. Без эмодзи. Без обращений «ты», «вы». Безлично.""",
        user_prompt=f"Вопрос: {question}\nЛунный день: {lunar_day}\nФаза: {phase_name}\nЗнак Луны: {moon_zodiac}\nОтвет:",
        temperature=0.8,
        user_id=current_user.email
    )

    with get_db() as conn:
        conn.execute(
            "INSERT INTO horoscope_questions (user_id, question_date, question, answer, zodiac_sign, period) VALUES (?, ?, ?, ?, ?, ?)",
            (current_user.email, today, question, ai_answer or '', f"Луна в {moon_zodiac}", f"{lunar_day}-й лунный день")
        )
        conn.commit()

    return jsonify({"question": question, "answer": ai_answer or "Звёзды пока молчат. Попробуйте перефразировать вопрос."})

# ---------- Вопрос по лунному дню (SSE-стрим) ----------
@moon_bp.route('/api/moon-calendar/ask/stream', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;50 per hour")
def api_moon_ask_stream():
    """
    SSE-стрим ответа на вопрос по лунному дню.

    Контракт:
        event: meta  → {question}
        event: chunk → {chunk: '...'}
        event: done  → {answer: '...'}
        event: error → {message}

    Логика сохранения в horoscope_questions — идентична старому
    api_moon_ask. Промпт — дословно оттуда же.
    """
    from flask import Response, stream_with_context
    from utils.ai_service import ask_deepseek_stream
    from utils.stream_helpers import format_sse
    from database.db import get_db
    from utils.helpers import today_msk

    if not current_user.is_authenticated or current_user.subscription != 'Пламя':
        return jsonify({"error": "Доступно на тарифе Пламя"}), 402

    data = request.json or {}
    question = data.get('question', '').strip()
    lunar_day = data.get('lunar_day')
    phase_name = data.get('phase_name')
    moon_zodiac = data.get('moon_zodiac')

    if not question:
        return jsonify({"error": "Напишите вопрос"}), 400
    if len(question) > 500:
        return jsonify({"error": "Вопрос слишком длинный (макс. 500 символов)"}), 400

    # Всё захватываем ДО генератора.
    user_id = current_user.email
    today = today_msk()

    system_prompt = f"""Ты — астролог и эксперт по лунному календарю. 
    Сегодня {lunar_day}-й лунный день, фаза: {phase_name}, Луна в знаке {moon_zodiac}.
    Ответь на вопрос, учитывая энергию этого лунного дня и знака Луны.
    3-5 предложений. Тёплый, заботливый тон. Без эмодзи. Без обращений «ты», «вы». Безлично."""

    user_prompt = f"Вопрос: {question}\nЛунный день: {lunar_day}\nФаза: {phase_name}\nЗнак Луны: {moon_zodiac}\nОтвет:"

    def generate():
        yield format_sse('meta', {'question': question})

        full_answer = ""
        try:
            for chunk in ask_deepseek_stream(system_prompt, user_prompt, temperature=0.8, user_id=user_id):
                if chunk is None:
                    break
                full_answer += chunk
                yield format_sse('chunk', {'chunk': chunk})
        except Exception:
            yield format_sse('error', {'message': 'Что-то пошло не так. Попробуйте ещё раз.'})
            return

        # Сохраняем в БД — как старый эндпоинт.
        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO horoscope_questions "
                    "(user_id, question_date, question, answer, zodiac_sign, period) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        user_id,
                        today,
                        question,
                        full_answer or '',
                        f"Луна в {moon_zodiac}",
                        f"{lunar_day}-й лунный день",
                    )
                )
                conn.commit()
        except Exception:
            # Ошибка сохранения — не критично для UX, но логируем.
            pass

        yield format_sse('done', {'answer': full_answer or "Звёзды пока молчат. Попробуйте перефразировать вопрос."})

    headers = {
        'Cache-Control': 'no-cache, no-transform',
        'X-Accel-Buffering': 'no',
    }
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers=headers,
    )

# ---------- AI-полная страница дня ----------
@moon_bp.route('/api/moon-calendar/ai-full', methods=['POST'])
@csrf_required
@limiter.limit("5 per minute;30 per hour")
def api_moon_day_ai_full():
    if not current_user.is_authenticated or current_user.subscription != 'Пламя':
        return jsonify({"error": "Доступно на тарифе Пламя"}), 402

    data = request.json or {}
    lunar_day = data.get('lunar_day')
    phase_name = data.get('phase_name')
    moon_zodiac = data.get('moon_zodiac')
    illumination = data.get('illumination', 0)

    if not all([lunar_day, phase_name, moon_zodiac]):
        return jsonify({"error": "Неверные параметры"}), 400

    user_name = current_user.name or ""
    user_zodiac = ""
    birth_date = current_user.birth_date or ""
    if birth_date:
        user_zodiac = get_zodiac_sign(birth_date) or ""

    portrait = get_or_create_portrait(current_user.email)
    user_themes = portrait.get('life_themes', [])
    user_tone = portrait.get('tone', '')
    user_coping = portrait.get('coping', '')

    result = ai_moon_day_full(
        lunar_day=lunar_day,
        phase_name=phase_name,
        moon_zodiac=moon_zodiac,
        illumination=illumination,
        user_name=user_name,
        user_zodiac=user_zodiac,
        user_themes=user_themes,
        user_tone=user_tone,
        user_coping=user_coping,
        user_id=current_user.email
    )

    if not result:
        return jsonify({"error": "Не удалось сгенерировать рекомендацию"}), 500

    return jsonify(result)

# ---------- AI-полная страница дня (SSE-стрим) ----------
@moon_bp.route('/api/moon-calendar/ai-full/stream', methods=['POST'])
@csrf_required
@limiter.limit("5 per minute;30 per hour")
def api_moon_day_ai_full_stream():
    """
    SSE-стрим полного AI-разбора лунного дня (только Пламя).

    Контракт:
        event: meta  → {lunar_day, phase_name, moon_zodiac}
        event: block → {name, value}
            name: recommendation, favorable, unfavorable, haircut, health,
                  ritual, guide_title, guide_energy, guide_advice,
                  guide_affirmation, guide_whisper
        event: done  → {}
        event: error → {message}

    Логика и промпт — те же, что в api_moon_day_ai_full.
    """
    from flask import Response, stream_with_context
    from utils.ai_service import ai_moon_day_full
    from utils.stream_helpers import format_sse

    if not current_user.is_authenticated or current_user.subscription != 'Пламя':
        return jsonify({"error": "Доступно на тарифе Пламя"}), 402

    data = request.json or {}
    lunar_day = data.get('lunar_day')
    phase_name = data.get('phase_name')
    moon_zodiac = data.get('moon_zodiac')
    illumination = data.get('illumination', 0)

    if not all([lunar_day, phase_name, moon_zodiac]):
        return jsonify({"error": "Неверные параметры"}), 400

    # Всё захватываем ДО генератора.
    user_name = current_user.name or ""
    user_zodiac = ""
    birth_date = current_user.birth_date or ""
    if birth_date:
        user_zodiac = get_zodiac_sign(birth_date) or ""

    portrait = get_or_create_portrait(current_user.email)
    user_themes = portrait.get('life_themes', [])
    user_tone = portrait.get('tone', '')
    user_coping = portrait.get('coping', '')
    user_email = current_user.email

    # Порядок блоков — как в ai_moon_day_full.
    block_keys = [
        'recommendation', 'favorable', 'unfavorable', 'haircut', 'health', 'ritual',
        'guide_title', 'guide_energy', 'guide_advice', 'guide_affirmation', 'guide_whisper',
    ]

    def generate():
        yield format_sse('meta', {
            'lunar_day': lunar_day,
            'phase_name': phase_name,
            'moon_zodiac': moon_zodiac,
        })

        try:
            result = ai_moon_day_full(
                lunar_day=lunar_day,
                phase_name=phase_name,
                moon_zodiac=moon_zodiac,
                illumination=illumination,
                user_name=user_name,
                user_zodiac=user_zodiac,
                user_themes=user_themes,
                user_tone=user_tone,
                user_coping=user_coping,
                user_id=user_email,
            )
        except Exception:
            yield format_sse('error', {'message': 'Не удалось сгенерировать рекомендацию'})
            return

        if not result:
            yield format_sse('error', {'message': 'Не удалось сгенерировать рекомендацию'})
            return

        for key in block_keys:
            value = result.get(key)
            if value:
                yield format_sse('block', {'name': key, 'value': value})

        yield format_sse('done', {})

    headers = {
        'Cache-Control': 'no-cache, no-transform',
        'X-Accel-Buffering': 'no',
    }
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers=headers,
    )

# ---------- Подсказки вопросов ----------
@moon_bp.route('/api/moon-calendar/suggestions', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;100 per hour")
def api_moon_suggestions():
    data = request.json or {}
    lunar_day = data.get('lunar_day')
    phase_name = data.get('phase_name', '')
    moon_zodiac = data.get('moon_zodiac', '')
    daily_text = data.get('daily_text', '')

    if not daily_text:
        return jsonify({"suggestions": [
            "Что этот лунный день значит именно для меня?",
            "Как использовать энергию дня?",
            "Почему важно учитывать фазу Луны?"
        ]})

    result = ai_moon_suggestions(lunar_day, phase_name, moon_zodiac, daily_text, user_id=get_identifier())

    if result:
        suggestions = [s.strip() for s in result.split('\n') if s.strip()][:3]
    else:
        suggestions = [
            "Что этот лунный день значит именно для меня?",
            "Как использовать энергию дня?",
            "Почему важно учитывать фазу Луны?"
        ]

    return jsonify({"suggestions": suggestions})

# ---------- Инфо для главной (портал) ----------
@moon_bp.route('/api/moon-calendar/info', methods=['POST'])
@csrf_required
@limiter.limit("20 per minute;200 per hour")
def api_moon_calendar_info():
    data = request.json or {}
    date_str = data.get('date', '')
    if not date_str:
        return jsonify({"error": "Укажите дату"}), 400
    detailed = get_user_access_level()
    result = get_moon_phase_full(date_str, detailed=detailed, timezone=data.get('timezone', 'Europe/Moscow'))
    return jsonify(result)

@moon_bp.route('/api/moon-calendar/panel', methods=['POST'])
@csrf_required
@limiter.limit("20 per minute;200 per hour")
def api_moon_calendar_panel():
    data = request.json or {}
    date_str = data.get('date', '')
    if not date_str:
        return jsonify({"error": "Укажите дату"}), 400
    timezone_str = data.get('timezone', 'Europe/Moscow')
    
    is_premium = current_user.is_authenticated and current_user.subscription == 'Пламя'
    result = get_moon_phase_for_panel(date_str, timezone=timezone_str, is_premium=is_premium)
    result['is_premium'] = is_premium
    
    return jsonify(result)