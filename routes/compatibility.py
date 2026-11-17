# routes/compatibility.py
from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user

from utils.calculators import calculate_compatibility
from utils.ai_service import ai_compatibility_suggestions, ai_compatibility_full
from utils.auth_core import csrf_required
from utils.extensions import limiter
from utils.helpers import get_user_access_level, get_identifier
from utils.orchestrator import get_or_create_portrait

compatibility_bp = Blueprint('compatibility', __name__)

@compatibility_bp.route('/compatibility')
def compatibility_page():
    return render_template('compatibility.html')

@compatibility_bp.route('/api/compatibility', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;100 per hour")
def api_compatibility():
    data = request.json or {}
    person1 = data.get('person1', {})
    person2 = data.get('person2', {})
    detailed = get_user_access_level()
    result = calculate_compatibility(
        person1, person2,
        detailed=detailed,
        user_id=get_identifier()
    )
    return jsonify(result)

@compatibility_bp.route('/api/compatibility/suggestions', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;100 per hour")
def api_compatibility_suggestions():
    data = request.json or {}
    full_text = data.get('full_text', '')
    if not full_text:
        return jsonify({"suggestions": [
            "А если бы даты рождения были другими?",
            "Что означает этот процент совместимости?",
            "Как улучшить взаимопонимание в паре?"
        ]})
    result = ai_compatibility_suggestions(full_text, user_id=get_identifier())
    if result:
        suggestions = [s.strip() for s in result.split('\n') if s.strip()][:3]
    else:
        suggestions = [
            "А если бы даты рождения были другими?",
            "Что означает этот процент совместимости?",
            "Как улучшить взаимопонимание в паре?"
        ]
    return jsonify({"suggestions": suggestions})

@compatibility_bp.route('/api/compatibility/ai-full', methods=['POST'])
@csrf_required
@limiter.limit("5 per minute;30 per hour")
def api_compatibility_ai_full():
    if not current_user.is_authenticated or current_user.subscription != 'Пламя':
        return jsonify({"error": "Доступно на тарифе Пламя"}), 402

    data = request.json or {}
    person1 = data.get('person1', {})
    person2 = data.get('person2', {})

    name1 = person1.get('name', '').strip()
    name2 = person2.get('name', '').strip()
    birth1 = person1.get('birth_date', '').strip()
    birth2 = person2.get('birth_date', '').strip()

    if not name1 or not name2:
        return jsonify({"error": "Введите имена обоих партнёров"}), 400

    # skip_ai_interpretation=True — не тратим токены на встроенный разбор,
    # разбор делает ai_compatibility_full ниже
    result = calculate_compatibility(
        person1, person2,
        detailed='plamya',
        skip_ai_interpretation=True,
        user_id=current_user.email
    )
    
    if 'error' in result:
        return jsonify({"error": result['error']}), 400

    portrait = get_or_create_portrait(current_user.email)
    user_themes = portrait.get('life_themes', [])
    user_tone = portrait.get('tone', '')
    user_coping = portrait.get('coping', '')
    
    ai_result = ai_compatibility_full(
        person1_name=name1,
        person1_birth=birth1,
        person2_name=name2,
        person2_birth=birth2,
        compatibility_percent=result.get('compatibility_percent', 50),
        verdict=result.get('verdict', 'Средняя совместимость'),
        user_tone=user_tone,
        user_coping=user_coping,
        user_themes=user_themes,
        user_id=current_user.email
    )

    if not ai_result:
        return jsonify({"error": "Не удалось сгенерировать разбор"}), 500

    ai_result['compatibility_percent'] = result.get('compatibility_percent', 50)
    ai_result['verdict'] = result.get('verdict', '')
    ai_result['person1'] = name1
    ai_result['person2'] = name2

    return jsonify(ai_result)

@compatibility_bp.route('/api/compatibility/ai-full/stream', methods=['POST'])
@csrf_required
@limiter.limit("5 per minute;30 per hour")
def api_compatibility_ai_full_stream():
    """
    SSE-стрим полного разбора совместимости (только Пламя).

    Контракт:
        event: meta  → {person1, person2, compatibility_percent, verdict}
        event: block → {name, value}   # по одному на каждое поле JSON
        event: done  → {}
        event: error → {message}

    Логика расчёта и промпты — те же, что в api_compatibility_ai_full
    (используется ai_compatibility_full с ask_deepseek_stream внутри).
    """
    from flask import Response, stream_with_context
    from utils.calculators import calculate_compatibility
    from utils.ai_service import ai_compatibility_full
    from utils.orchestrator import get_or_create_portrait
    from utils.stream_helpers import format_sse

    if not current_user.is_authenticated or current_user.subscription != 'Пламя':
        return jsonify({"error": "Доступно на тарифе Пламя"}), 402

    data = request.json or {}
    person1 = data.get('person1', {})
    person2 = data.get('person2', {})

    name1 = person1.get('name', '').strip()
    name2 = person2.get('name', '').strip()
    birth1 = person1.get('birth_date', '').strip()
    birth2 = person2.get('birth_date', '').strip()

    if not name1 or not name2:
        return jsonify({"error": "Введите имена обоих партнёров"}), 400

    # Быстрый расчёт без AI.
    calc_result = calculate_compatibility(
        person1, person2,
        detailed='plamya',
        skip_ai_interpretation=True,
        user_id=current_user.email,
    )
    if 'error' in calc_result:
        return jsonify({"error": calc_result['error']}), 400

    # Портрет — берём один раз до генератора.
    portrait = get_or_create_portrait(current_user.email)
    user_themes = portrait.get('life_themes', [])
    user_tone = portrait.get('tone', '')
    user_coping = portrait.get('coping', '')
    user_email = current_user.email

    compat_percent = calc_result.get('compatibility_percent', 50)
    verdict = calc_result.get('verdict', 'Средняя совместимость')

    # Поля JSON, которые придут от AI. Список — тот же, что в ai_compatibility_full.
    json_fields = [
        'names', 'birth', 'destiny', 'karma', 'love',
        'household', 'finance', 'conclusion',
        'strengths', 'challenges', 'advice',
    ]

    def generate():
        yield format_sse('meta', {
            'person1': name1,
            'person2': name2,
            'compatibility_percent': compat_percent,
            'verdict': verdict,
        })

        # Полный разбор через ai_compatibility_full, но с использованием
        # ask_deepseek_stream внутри — собираем весь JSON в буфер.
        # Отдаём после получения: по одному block на поле.
        try:
            # ai_compatibility_full возвращает dict (уже распарсенный JSON).
            # Внутри она использует ask_deepseek (не stream) — см. utils/ai_service.py.
            # Поэтому используем её напрямую: результат — тот же, что в api_compatibility_ai_full.
            ai_result = ai_compatibility_full(
                person1_name=name1,
                person1_birth=birth1,
                person2_name=name2,
                person2_birth=birth2,
                compatibility_percent=compat_percent,
                verdict=verdict,
                user_tone=user_tone,
                user_coping=user_coping,
                user_themes=user_themes,
                user_id=user_email,
            )
        except Exception:
            yield format_sse('error', {'message': 'Не удалось сгенерировать разбор'})
            return

        if not ai_result:
            yield format_sse('error', {'message': 'Не удалось сгенерировать разбор'})
            return

        # Отдаём блоки по одному — по мере готовности полей.
        # Порядок фиксирован, чтобы фронт мог рендерить карточки последовательно.
        for field_name in json_fields:
            value = ai_result.get(field_name)
            if value:
                yield format_sse('block', {'name': field_name, 'value': value})

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