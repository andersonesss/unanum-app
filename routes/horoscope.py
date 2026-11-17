# routes/horoscope.py
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from database.db import get_db
from utils.calculators import get_daily_horoscope
from utils.ai_service import ai_horoscope_answer, ai_horoscope_suggestions
from utils.auth_core import csrf_required
from utils.extensions import limiter
from utils.helpers import get_identifier, get_user_access_level, today_msk
from utils.orchestrator import get_or_create_portrait

horoscope_bp = Blueprint('horoscope', __name__)

# ---------- Страница ----------
@horoscope_bp.route('/horoscope')
def horoscope_page():
    return render_template('horoscope.html')

# ---------- Получить гороскоп (JSON-fallback для старых клиентов) ----------
@horoscope_bp.route('/api/horoscope', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;100 per hour")
def api_horoscope():
    """Полный гороскоп одним JSON-ответом (не SSE) — fallback для старых клиентов."""
    data = request.json or {}
    zodiac_sign = data.get('zodiac_sign', '').strip()
    period = data.get('period', 'день')

    if not zodiac_sign:
        return jsonify({"error": "Не указан знак зодиака"}), 400

    detailed = get_user_access_level()
    is_plamya = (detailed == 'plamya')
    user_id = get_identifier()

    result = get_daily_horoscope(zodiac_sign, detailed=is_plamya, period=period, user_id=user_id)
    return jsonify(result)

# ---------- Получить гороскоп ----------
@horoscope_bp.route('/api/horoscope/stream', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;100 per hour")
def api_horoscope_stream():
    """
    SSE-стрим гороскопа. Блоки (description, daily, love, career, health,
    daily_advice) приходят по мере готовности параллельных AI-задач.

    Контракт событий:
        event: meta  → {sign, emoji, element, period, period_type, extra, planned_blocks}
        event: block → {name, value, [teaser], [short], [full]}
        event: done  → {period_type}
        event: error → {message}
    """
    from flask import Response, stream_with_context

    data = request.json or {}
    zodiac_sign = data.get('zodiac_sign', '').strip()
    period = data.get('period', 'день')

    if not zodiac_sign:
        return jsonify({"error": "Не указан знак зодиака"}), 400

    detailed = get_user_access_level()
    is_plamya = (detailed == 'plamya')
    user_id = get_identifier()

    # Импорты, нужные внутри генератора, читаем заранее — чтобы импорт
    # произошёл при активном flask-контексте (внутри генератора уже нельзя).
    from utils.calculators import get_daily_horoscope_stream
    from utils.stream_helpers import format_sse

    def generate():
        try:
            for event_type, event_data in get_daily_horoscope_stream(
                zodiac_sign,
                detailed=is_plamya,
                period=period,
                user_id=user_id,
            ):
                yield format_sse(event_type, event_data)
            yield format_sse('done', {'period_type': period})
        except Exception:
            yield format_sse('error', {'message': 'Не удалось построить гороскоп. Попробуйте ещё раз.'})

    headers = {
        'Cache-Control': 'no-cache, no-transform',
        'X-Accel-Buffering': 'no',
    }
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers=headers,
    )

# ---------- Задать вопрос ----------
@horoscope_bp.route('/api/horoscope/ask', methods=['POST'])
@login_required
@csrf_required
@limiter.limit("10 per minute;50 per hour")
def api_horoscope_ask():
    data = request.json or {}
    question = data.get('question', '').strip()
    zodiac_sign = data.get('zodiac_sign', '')
    period = data.get('period', 'день')

    if not question:
        return jsonify({"error": "Напиши вопрос"}), 400
    if len(question) > 500:
        return jsonify({"error": "Вопрос слишком длинный (макс. 500 символов)"}), 400

    today = today_msk()
    limit = current_user.get_question_limit()

    # Проверка лимита ДО вызова AI — иначе токены DeepSeek тратятся впустую
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM horoscope_questions WHERE user_id = ? AND question_date = ?",
            (current_user.email, today)
        ).fetchone()
        count = row['cnt'] if row else 0

        if limit is not None and count >= limit:
            return jsonify({
                "error": f"Дневной лимит исчерпан ({limit} вопросов).",
                "current_tariff": current_user.get_tariff_name(),
                "upgrade_tariff": "Пламя"
            }), 402

        # Лимит не исчерпан — вызываем AI
        answer = ai_horoscope_answer(
            zodiac_sign, period, question,
            user_id=current_user.email
        ) or "Звёзды пока молчат. Попробуй перефразировать вопрос."

        conn.execute(
            "INSERT INTO horoscope_questions (user_id, question_date, question, answer, zodiac_sign, period) VALUES (?, ?, ?, ?, ?, ?)",
            (current_user.email, today, question, answer, zodiac_sign, period)
        )
        conn.commit()

    if limit is None:
        remaining = "безлимит"
        limit_text = "безлимит"
    else:
        remaining = limit - count - 1
        limit_text = limit

    return jsonify({
        "question": question,
        "answer": answer,
        "remaining": remaining,
        "limit": limit_text
    })

# ---------- Подсказки вопросов ----------
@horoscope_bp.route('/api/horoscope/suggestions', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;100 per hour")
def api_horoscope_suggestions():
    data = request.json or {}
    zodiac_sign = data.get('zodiac_sign', '')
    daily_text = data.get('daily_text', '')

    if not daily_text:
        return jsonify({"suggestions": [
            "Что меня ждёт в любви?",
            "Стоит ли менять работу?",
            "Как пройдёт эта неделя?"
        ]})

    user_context = {}
    if current_user.is_authenticated:
        user_context['name'] = current_user.name or ''
        user_context['tariff'] = current_user.subscription or 'Искра'
        portrait = get_or_create_portrait(current_user.email)
        user_context['themes'] = portrait.get('life_themes', [])
    else:
        user_context['tariff'] = 'Искра'

    result = ai_horoscope_suggestions(zodiac_sign, daily_text, user_context, user_id=get_identifier())

    if result:
        suggestions = [s.strip() for s in result.split('\n') if s.strip()][:3]
    else:
        suggestions = [
            "Что меня ждёт в любви?",
            "Стоит ли менять работу?",
            "Как пройдёт эта неделя?"
        ]

    return jsonify({"suggestions": suggestions})