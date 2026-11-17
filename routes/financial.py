# routes/financial.py
from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user

from utils.calculators import calculate_financial_code, get_daily_financial_advice
from utils.ai_service import ai_financial_suggestions
from utils.orchestrator import get_or_create_portrait
from utils.auth_core import csrf_required
from utils.extensions import limiter
from utils.helpers import get_user_access_level, get_zodiac_sign, get_identifier

financial_bp = Blueprint('financial', __name__)

# ---------- Страница ----------
@financial_bp.route('/financial-code')
def financial_code_page():
    return render_template('financial_code.html')

# ---------- Расчёт кода ----------
@financial_bp.route('/api/financial-code', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;100 per hour")
def api_financial_code():
    data = request.json or {}
    birth_date = data.get('birth_date', '')
    identifier = get_identifier()
    detailed = get_user_access_level()
    result = calculate_financial_code(birth_date, detailed=detailed, user_id=identifier)
    
    # Генерируем ежедневный совет
    if result.get('code') and result.get('digits_breakdown'):
        try:
            daily_advice = get_daily_financial_advice(
                code=result['code'],
                digits_breakdown=result['digits_breakdown'],
                user_id=identifier,
                detailed=detailed
            )
            if daily_advice:
                result["daily_advice_short"] = daily_advice.get('short', '')
                result["daily_advice_full"] = daily_advice.get('full', '')
        except Exception:
            pass
    
    return jsonify(result)

# ---------- Расчёт кода (SSE-стрим) ----------
@financial_bp.route('/api/financial-code/stream', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;100 per hour")
def api_financial_code_stream():
    """
    SSE-стрим финансового кода.

    Контракт событий:
        event: meta  → {code, digits_breakdown, planned_blocks, is_plamya, upgrade_hint}
        event: chunk → {chunk, name, phase}   # name='digit_0'..'digit_3' и т.д.
        event: block → {name, value}          # финальное значение блока
        event: done  → {code}
        event: error → {message}

    Пример потока:
        1. meta  — код + 4 цифры + список задач (мгновенно)
        2. chunk × N phase='teaser', name='digit_0'   — быстрые первые буквы
        3. chunk × N phase='full',   name='digit_0'   — полный разбор цифры
        4. block 'digit_0'                            — финал цифры 0
        ...
        5. block 'summary', 'life_path_link', [премиум]
        6. done

    Старый эндпоинт /api/financial-code остаётся — он отдаёт тот же
    результат одним JSON-ответом (без стриминга).
    """
    from flask import Response, stream_with_context

    data = request.json or {}
    birth_date = data.get('birth_date', '').strip()

    if not birth_date:
        return jsonify({"error": "Не указана дата рождения"}), 400

    # get_user_access_level() возвращает:
    #   'plamya' — залогинен, тариф Пламя
    #   'brief'  — залогинен Искра или гость
    # calculate_financial_code_stream корректно обрабатывает все варианты.
    detailed = get_user_access_level()
    # Гость → отдельный уровень 'guest': calculate_financial_code_stream
    # вернёт только код + upgrade_hint, без AI-вызовов. Без этой проверки
    # гость получал 'brief' и тратил 10 вызовов DeepSeek впустую
    # (4 teaser + 4 full + summary + life_path_link), а full-тексты
    # всё равно отбрасывались на фронте (renderFinCodeTeaserBlocks).
    # Паттерн — как в routes/moon.py:api_moon_calendar_month.
    if detailed == 'brief' and not current_user.is_authenticated:
        detailed = 'guest'
    user_id = get_identifier()

    # Импорты внутри функции — чтобы не тянуть их в шапку модуля
    # (шапка уже импортирует не-стрим версию).
    from utils.calculators import calculate_financial_code_stream
    from utils.stream_helpers import format_sse

    def generate():
        try:
            for event_type, event_data in calculate_financial_code_stream(
                birth_date,
                detailed=detailed,
                user_id=user_id,
            ):
                yield format_sse(event_type, event_data)
        except Exception:
            yield format_sse('error', {
                'message': 'Не удалось построить финансовый код. Попробуйте ещё раз.'
            })

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
@financial_bp.route('/api/financial-code/suggestions', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;100 per hour")
def api_financial_code_suggestions():
    data = request.json or {}
    full_text = data.get('full_text', '')
    if not full_text:
        return jsonify({"suggestions": [
            "Что означает первая цифра моего кода?",
            "Как код влияет на мою карьеру?",
            "А если бы я родился на день позже?"
        ]})
    user_context = {}
    if current_user.is_authenticated:
        user_context['name'] = current_user.name or ''
        user_context['tariff'] = current_user.subscription or 'Искра'
        portrait = get_or_create_portrait(current_user.email)
        user_context['themes'] = portrait.get('life_themes', [])
        if current_user.birth_date:
            try:
                zodiac = get_zodiac_sign(current_user.birth_date)
                if zodiac:
                    user_context['zodiac'] = zodiac
            except:
                pass
    else:
        user_context['tariff'] = 'Искра'

    result = ai_financial_suggestions(full_text, user_context, user_id=get_identifier())
    if result:
        suggestions = [s.strip() for s in result.split('\n') if s.strip()][:3]
    else:
        suggestions = [
            "Что означает первая цифра моего кода?",
            "Как код влияет на мою карьеру?",
            "А если бы я родился на день позже?"
        ]
    return jsonify({"suggestions": suggestions})