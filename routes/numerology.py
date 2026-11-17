# routes/numerology.py
from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user

from datetime import datetime
from utils.helpers import get_user_access_level, get_identifier
from utils.calculators import calculate_numerology_full, calculate_life_graph
from utils.ai_service import (
    ai_numerology_suggestions, ai_psychomatrix_suggestions, ai_life_graph_suggestions,
    ai_numerology_portrait, ai_psychomatrix_full, ai_psychomatrix_teaser,
    ai_life_graph_full, ai_life_graph_teaser
)
from utils.orchestrator import get_or_create_portrait
from utils.auth_core import csrf_required
from utils.extensions import limiter

numerology_bp = Blueprint('numerology', __name__)

@numerology_bp.route('/numerology')
def numerology_page():
    return render_template('numerology.html')

@numerology_bp.route('/api/numerology', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;100 per hour")
def api_numerology():
    data = request.json or {}
    birth_date = data.get('birth_date', '')
    first_name = data.get('first_name', '')
    last_name = data.get('last_name', '')
    middle_name = data.get('middle_name', '')
    detailed = get_user_access_level()
    result = calculate_numerology_full(first_name, last_name, middle_name, birth_date, detailed, user_id=get_identifier())
    return jsonify(result)

@numerology_bp.route('/api/numerology/psychomatrix', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;100 per hour")
def api_psychomatrix():
    from utils.helpers import now_msk
    data = request.json or {}
    birth_date = data.get('birth_date', '')
    
    try:
        dt = datetime.strptime(birth_date, '%Y-%m-%d')
        if dt > now_msk().replace(tzinfo=None):
            return jsonify({"error": "Дата рождения не может быть в будущем"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Неверный формат даты"}), 400
    
    result = calculate_numerology_full('', '', '', birth_date, detailed='plamya', user_id=get_identifier())
    
    if 'error' in result:
        return jsonify({"error": result['error']}), 400
    
    cells = result.get('pythagoras', {}).get('cells', {})
    lines_raw = result.get('pythagoras', {}).get('lines', {})
    
    line_descs = {
        "purpose": "Строка 1·4·7 — насколько человек ставит цель и доводит её до конца.",
        "family": "Строка 2·5·8 — тяга к дому, паре, заботе о близких.",
        "stability": "Строка 3·6·9 — нужен привычный уклад или тянет к переменам.",
        "self_esteem": "Столбец 1·2·3 — насколько человек верит в себя без оглядки на чужое одобрение.",
        "money": "Столбец 4·5·6 — отношение к заработку и бытовому комфорту.",
        "talent": "Столбец 7·8·9 — заложен яркий дар или способности раскрываются трудом.",
        "spirituality": "Диагональ 1·5·9 — интерес к смыслу, самопознанию, внутренней работе.",
        "temperament": "Диагональ 3·5·7 — сила чувств: от сдержанности до страсти."
    }
    
    lines = {}
    for key, raw_line in lines_raw.items():
        if isinstance(raw_line, str) and ':' in raw_line:
            name = raw_line.split(':')[0].strip()
            value_str = raw_line.split(':')[1].strip()
            value = len(value_str) if value_str.replace('—', '') else 0
        else:
            name = key
            value = 0
        lines[key] = {
            "name": name,
            "desc": line_descs.get(key, ''),
            "value": value
        }
    
    return jsonify({"cells": cells, "lines": lines})


@numerology_bp.route('/api/numerology/suggestions', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;100 per hour")
def api_numerology_suggestions():
    data = request.json or {}
    full_text = data.get('full_text', '')
    if not full_text:
        return jsonify({"suggestions": [
            "Что означает сочетание этих чисел для личной жизни?",
            "Какие профессии подходят под эти числа?",
            "Как улучшить финансовое положение с такими числами?"
        ]})
    
    result = ai_numerology_suggestions(full_text, user_id=get_identifier())
    if result:
        suggestions = [s.strip() for s in result.split('\n') if s.strip()][:3]
    else:
        suggestions = [
            "Что означает сочетание этих чисел для личной жизни?",
            "Какие профессии подходят под эти числа?",
            "Как улучшить финансовое положение с такими числами?"
        ]
    return jsonify({"suggestions": suggestions})


@numerology_bp.route('/api/numerology/ai-full', methods=['POST'])
@csrf_required
@limiter.limit("5 per minute;30 per hour")
def api_numerology_ai_full():
    if not current_user.is_authenticated or current_user.subscription != 'Пламя':
        return jsonify({"error": "Доступно на тарифе Пламя"}), 402

    data = request.json or {}
    first_name = data.get('first_name', '')
    last_name = data.get('last_name', '')
    middle_name = data.get('middle_name', '')
    birth_date = data.get('birth_date', '')

    if not birth_date:
        return jsonify({"error": "Дата рождения обязательна"}), 400

    result = calculate_numerology_full(first_name, last_name, middle_name, birth_date, detailed='plamya', user_id=current_user.email)
    
    if 'error' in result:
        return jsonify({"error": result['error']}), 400

    full_name = f"{last_name} {first_name} {middle_name}".strip() or first_name
    
    portrait = get_or_create_portrait(current_user.email)
    user_themes = portrait.get('life_themes', [])
    user_tone = portrait.get('tone', '')

    ai_result = ai_numerology_portrait(
        name=full_name,
        birth_date=birth_date,
        life_path=result.get('life_path', {}).get('number', '?'),
        destiny=result.get('destiny', {}).get('number', '?'),
        soul=result.get('soul_date', {}).get('number', '?'),
        personality=result.get('personality', {}).get('number', '?'),
        maturity=result.get('maturity', {}).get('number', '?'),
        expression=result.get('expression', {}).get('number', '?'),
        soul_urge=result.get('soul_name', {}).get('number', '?'),
        detailed=True,
        user_tone=user_tone,
        user_themes=user_themes,
        user_id=current_user.email
    )

    if not ai_result:
        return jsonify({"error": "Не удалось сгенерировать портрет"}), 500

    return jsonify(ai_result)

@numerology_bp.route('/api/numerology/ai-full/stream', methods=['POST'])
@csrf_required
@limiter.limit("5 per minute;30 per hour")
def api_numerology_ai_full_stream():
    """
    SSE-стрим полного нумерологического портрета (только Пламя).

    Контракт:
        event: meta  → {numbers: {life_path, destiny, soul, personality,
                                   maturity, expression, soul_urge}}
        event: block → {name, value}
            value = {meaning, strengths, challenges} для аспектов
            value = 'строка'                          для summary
        event: done  → {}
        event: error → {message}

    Все AI-задачи собираются в один вызов ai_numerology_portrait (как в
    api_numerology_ai_full). Стрим здесь — только транспорт: meta (числа
    без AI) + блоки по аспектам, полученные из JSON.
    """
    from flask import Response, stream_with_context
    from utils.calculators import calculate_numerology_full
    from utils.ai_service import ai_numerology_portrait
    from utils.orchestrator import get_or_create_portrait
    from utils.stream_helpers import format_sse

    if not current_user.is_authenticated or current_user.subscription != 'Пламя':
        return jsonify({"error": "Доступно на тарифе Пламя"}), 402

    data = request.json or {}
    first_name = data.get('first_name', '')
    last_name = data.get('last_name', '')
    middle_name = data.get('middle_name', '')
    birth_date = data.get('birth_date', '')

    if not birth_date:
        return jsonify({"error": "Дата рождения обязательна"}), 400

    # Числа без AI (новый режим).
    numbers_result = calculate_numerology_full(
        first_name, last_name, middle_name, birth_date,
        detailed='numbers_only',
        user_id=current_user.email,
    )
    if 'error' in numbers_result:
        return jsonify({"error": numbers_result['error']}), 400

    full_name = f"{last_name} {first_name} {middle_name}".strip() or first_name

    portrait = get_or_create_portrait(current_user.email)
    user_themes = portrait.get('life_themes', [])
    user_tone = portrait.get('tone', '')

    # Собираем числа для meta — те же ключи, что ждёт фронт (см. calculatePortrait
    # в templates/numerology.html: numbers.life_path, .destiny, .soul, ...).
    numbers_for_meta = {
        'life_path':   numbers_result.get('life_path', {}).get('number', ''),
        'destiny':     numbers_result.get('destiny', {}).get('number', ''),
        'soul':        numbers_result.get('soul_date', {}).get('number', ''),
        'personality': numbers_result.get('personality', {}).get('number', ''),
        'maturity':    numbers_result.get('maturity', {}).get('number', ''),
        'expression':  numbers_result.get('expression', {}).get('number', ''),
        'soul_urge':   numbers_result.get('soul_name', {}).get('number', ''),
    }

    # Поля JSON, которые придут от AI. Порядок соответствует
    # ai_numerology_portrait(detailed=True).
    aspect_keys = ['life_path', 'destiny', 'soul', 'personality',
                   'maturity', 'expression', 'soul_urge']

    user_email = current_user.email

    def generate():
        yield format_sse('meta', {'numbers': numbers_for_meta})

        try:
            ai_result = ai_numerology_portrait(
                name=full_name,
                birth_date=birth_date,
                life_path=numbers_for_meta['life_path'] or '?',
                destiny=numbers_for_meta['destiny'] or '?',
                soul=numbers_for_meta['soul'] or '?',
                personality=numbers_for_meta['personality'] or '?',
                maturity=numbers_for_meta['maturity'] or '?',
                expression=numbers_for_meta['expression'] or '?',
                soul_urge=numbers_for_meta['soul_urge'] or '?',
                detailed=True,
                user_tone=user_tone,
                user_themes=user_themes,
                user_id=user_email,
            )
        except Exception:
            yield format_sse('error', {'message': 'Не удалось сгенерировать портрет'})
            return

        if not ai_result:
            yield format_sse('error', {'message': 'Не удалось сгенерировать портрет'})
            return

        # Отдаём по одному блоку на аспект + summary.
        for key in aspect_keys:
            value = ai_result.get(key)
            if value:
                yield format_sse('block', {'name': key, 'value': value})

        if ai_result.get('summary'):
            yield format_sse('block', {'name': 'summary', 'value': ai_result['summary']})

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

@numerology_bp.route('/api/numerology/teaser', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;50 per hour")
def api_numerology_teaser():
    data = request.json or {}
    first_name = data.get('first_name', '')
    last_name = data.get('last_name', '')
    middle_name = data.get('middle_name', '')
    birth_date = data.get('birth_date', '')

    if not birth_date:
        return jsonify({"error": "Дата рождения обязательна"}), 400

    result = calculate_numerology_full(first_name, last_name, middle_name, birth_date, detailed='plamya', user_id=get_identifier())
    
    if 'error' in result:
        return jsonify({"error": result['error']}), 400

    full_name = f"{last_name} {first_name} {middle_name}".strip() or first_name

    ai_result = ai_numerology_portrait(
        name=full_name,
        birth_date=birth_date,
        life_path=result.get('life_path', {}).get('number', '?'),
        destiny=result.get('destiny', {}).get('number', '?'),
        soul=result.get('soul_date', {}).get('number', '?'),
        personality=result.get('personality', {}).get('number', '?'),
        maturity=result.get('maturity', {}).get('number', '?'),
        expression=result.get('expression', {}).get('number', '?'),
        soul_urge=result.get('soul_name', {}).get('number', '?'),
        detailed=False,
        user_id=get_identifier()
    )

    if not ai_result:
        return jsonify({"error": "Не удалось сгенерировать тизеры"}), 500

    ai_result['numbers'] = {
        'life_path': result.get('life_path', {}).get('number'),
        'destiny': result.get('destiny', {}).get('number'),
        'soul': result.get('soul_date', {}).get('number'),
        'personality': result.get('personality', {}).get('number'),
        'maturity': result.get('maturity', {}).get('number'),
        'expression': result.get('expression', {}).get('number'),
        'soul_urge': result.get('soul_name', {}).get('number'),
    }

    return jsonify(ai_result)


@numerology_bp.route('/api/numerology/psychomatrix/ai-full', methods=['POST'])
@csrf_required
@limiter.limit("5 per minute;30 per hour")
def api_psychomatrix_ai_full():
    if not current_user.is_authenticated or current_user.subscription != 'Пламя':
        return jsonify({"error": "Доступно на тарифе Пламя"}), 402

    data = request.json or {}
    birth_date = data.get('birth_date', '')

    if not birth_date:
        return jsonify({"error": "Дата рождения обязательна"}), 400

    result = calculate_numerology_full('', '', '', birth_date, detailed='plamya', user_id=current_user.email)
    
    cells = []
    if 'pythagoras' in result:
        for i in range(1, 10):
            cell = result['pythagoras']['cells'].get(f'cell{i}', {})
            cells.append({
                'num': i,
                'name': cell.get('name', ''),
                'value': cell.get('value', '—'),
                'count': cell.get('count', 0)
            })

    portrait = get_or_create_portrait(current_user.email)
    user_themes = portrait.get('life_themes', [])
    user_tone = portrait.get('tone', '')
    user_coping = portrait.get('coping', '')

    pythagoras = result.get('pythagoras', {})
    cells_dict = pythagoras.get('cells', {})
    counts = {i: cells_dict.get(f'cell{i}', {}).get('count', 0) for i in range(1, 10)}
    
    line_names = ['Целеустремлённость', 'Семья', 'Стабильность', 'Самооценка', 'Деньги и быт', 'Талант', 'Духовность', 'Темперамент']
    line_values = [
        counts[1]+counts[4]+counts[7],
        counts[2]+counts[5]+counts[8],
        counts[3]+counts[6]+counts[9],
        counts[1]+counts[2]+counts[3],
        counts[4]+counts[5]+counts[6],
        counts[7]+counts[8]+counts[9],
        counts[1]+counts[5]+counts[9],
        counts[3]+counts[5]+counts[7]
    ]
    lines_for_ai = [{'name': line_names[i], 'value': line_values[i]} for i in range(8)]

    ai_result = ai_psychomatrix_full(
        name=current_user.name or '',
        birth_date=birth_date,
        cells=cells,
        lines=lines_for_ai,
        user_tone=user_tone,
        user_coping=user_coping,
        user_themes=user_themes,
        user_id=current_user.email
    )
    if not ai_result:
        return jsonify({"error": "Не удалось сгенерировать разбор"}), 500
    return jsonify(ai_result)

@numerology_bp.route('/api/numerology/psychomatrix/ai-full/stream', methods=['POST'])
@csrf_required
@limiter.limit("5 per minute;30 per hour")
def api_psychomatrix_ai_full_stream():
    """
    SSE-стрим полного разбора психоматрицы (только Пламя).

    Контракт:
        event: meta  → {birth_date}
        event: block → {name, value}
            name: cell1..cell9, line1..line8, summary, lines_summary
        event: done  → {}
        event: error → {message}

    Промпт и логика расчёта — те же, что в api_psychomatrix_ai_full.
    Стрим здесь транспорт: meta (мгновенно) + блоки после получения JSON.
    """
    from flask import Response, stream_with_context
    from utils.calculators import calculate_numerology_full
    from utils.ai_service import ai_psychomatrix_full
    from utils.orchestrator import get_or_create_portrait
    from utils.stream_helpers import format_sse

    if not current_user.is_authenticated or current_user.subscription != 'Пламя':
        return jsonify({"error": "Доступно на тарифе Пламя"}), 402

    data = request.json or {}
    birth_date = data.get('birth_date', '')
    if not birth_date:
        return jsonify({"error": "Дата рождения обязательна"}), 400

    # Числа без AI — режим numbers_only (см. Правку E1).
    result = calculate_numerology_full(
        '', '', '', birth_date,
        detailed='numbers_only',
        user_id=current_user.email,
    )
    if 'error' in result:
        return jsonify({"error": result['error']}), 400

    # cells — как в api_psychomatrix_ai_full.
    cells = []
    for i in range(1, 10):
        cell = result.get('pythagoras', {}).get('cells', {}).get(f'cell{i}', {})
        cells.append({
            'num': i,
            'name': cell.get('name', ''),
            'value': cell.get('value', '—'),
            'count': cell.get('count', 0),
        })

    # lines_for_ai — те же имена и значения, что в api_psychomatrix_ai_full.
    pythagoras = result.get('pythagoras', {})
    cells_dict = pythagoras.get('cells', {})
    counts = {i: cells_dict.get(f'cell{i}', {}).get('count', 0) for i in range(1, 10)}

    line_names = ['Целеустремлённость', 'Семья', 'Стабильность', 'Самооценка',
                  'Деньги и быт', 'Талант', 'Духовность', 'Темперамент']
    line_values = [
        counts[1] + counts[4] + counts[7],
        counts[2] + counts[5] + counts[8],
        counts[3] + counts[6] + counts[9],
        counts[1] + counts[2] + counts[3],
        counts[4] + counts[5] + counts[6],
        counts[7] + counts[8] + counts[9],
        counts[1] + counts[5] + counts[9],
        counts[3] + counts[5] + counts[7],
    ]
    lines_for_ai = [{'name': line_names[i], 'value': line_values[i]} for i in range(8)]

    portrait = get_or_create_portrait(current_user.email)
    user_themes = portrait.get('life_themes', [])
    user_tone = portrait.get('tone', '')
    user_coping = portrait.get('coping', '')
    user_email = current_user.email
    user_name = current_user.name or ''

    cell_block_keys = [f'cell{i}' for i in range(1, 10)]
    line_block_keys = [f'line{i}' for i in range(1, 9)]

    def generate():
        yield format_sse('meta', {'birth_date': birth_date})

        try:
            ai_result = ai_psychomatrix_full(
                name=user_name,
                birth_date=birth_date,
                cells=cells,
                lines=lines_for_ai,
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

        # Ячейки, линии, оба summary — порядок фиксирован.
        for key in cell_block_keys:
            value = ai_result.get(key)
            if value:
                yield format_sse('block', {'name': key, 'value': value})

        for key in line_block_keys:
            value = ai_result.get(key)
            if value:
                yield format_sse('block', {'name': key, 'value': value})

        if ai_result.get('summary'):
            yield format_sse('block', {'name': 'summary', 'value': ai_result['summary']})
        if ai_result.get('lines_summary'):
            yield format_sse('block', {'name': 'lines_summary', 'value': ai_result['lines_summary']})

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

@numerology_bp.route('/api/numerology/psychomatrix/teaser', methods=['POST'])
@csrf_required
def api_psychomatrix_teaser():
    data = request.json or {}
    birth_date = data.get('birth_date', '')

    if not birth_date:
        return jsonify({"error": "Дата рождения обязательна"}), 400

    result = calculate_numerology_full('', '', '', birth_date, detailed='plamya', user_id=get_identifier())
    
    cells = []
    if 'pythagoras' in result:
        for i in range(1, 10):
            cell = result['pythagoras']['cells'].get(f'cell{i}', {})
            cells.append({
                'num': i,
                'name': cell.get('name', ''),
                'value': cell.get('value', '—'),
                'count': cell.get('count', 0)
            })

    ai_result = ai_psychomatrix_teaser(
        name=data.get('first_name', ''),
        birth_date=birth_date,
        cells=cells,
        user_id=get_identifier()
    )

    if not ai_result:
        return jsonify({"error": "Не удалось сгенерировать тизеры"}), 500

    return jsonify(ai_result)


@numerology_bp.route('/api/numerology/life-graph/ai-full', methods=['POST'])
@csrf_required
@limiter.limit("5 per minute;30 per hour")
def api_life_graph_ai_full():
    if not current_user.is_authenticated or current_user.subscription != 'Пламя':
        return jsonify({"error": "Доступно на тарифе Пламя"}), 402

    data = request.json or {}
    birth_date = data.get('birth_date', '')
    if not birth_date:
        return jsonify({"error": "Дата рождения обязательна"}), 400

    graph_data = calculate_life_graph(birth_date)
    if 'error' in graph_data:
        return jsonify({"error": graph_data['error']}), 400
    
    graph_code = graph_data['code']
    cycles = graph_data['cycles']
    current_period = graph_data['current_period']
    current_level = graph_data['current_level']
    current_start = graph_data['current_start']
    current_end = graph_data['current_end']

    portrait = get_or_create_portrait(current_user.email)
    user_themes = portrait.get('life_themes', [])
    user_tone = portrait.get('tone', '')

    ai_result = ai_life_graph_full(
        name=current_user.name or '',
        birth_date=birth_date,
        cycles=cycles,
        current_level=current_level,
        current_age_start=current_start,
        current_age_end=current_end,
        user_tone=user_tone,
        user_themes=user_themes,
        user_id=current_user.email
    )

    if not ai_result:
        return jsonify({"error": "Не удалось сгенерировать разбор"}), 500

    return jsonify(ai_result)

@numerology_bp.route('/api/numerology/life-graph/ai-full/stream', methods=['POST'])
@csrf_required
@limiter.limit("5 per minute;30 per hour")
def api_life_graph_ai_full_stream():
    """
    SSE-стрим разбора графика жизни (только Пламя).

    Контракт:
        event: meta  → {code, cycles, current_period, current_level,
                         current_start, current_end}
        event: block → {name, value}
            name: overview, current, period0..period6, advice
        event: done  → {}
        event: error → {message}

    Логика расчёта и промпт — те же, что в api_life_graph_ai_full.
    """
    from flask import Response, stream_with_context
    from utils.calculators import calculate_life_graph
    from utils.ai_service import ai_life_graph_full
    from utils.orchestrator import get_or_create_portrait
    from utils.stream_helpers import format_sse

    if not current_user.is_authenticated or current_user.subscription != 'Пламя':
        return jsonify({"error": "Доступно на тарифе Пламя"}), 402

    data = request.json or {}
    birth_date = data.get('birth_date', '')
    if not birth_date:
        return jsonify({"error": "Дата рождения обязательна"}), 400

    graph_data = calculate_life_graph(birth_date)
    if 'error' in graph_data:
        return jsonify({"error": graph_data['error']}), 400

    graph_code = graph_data['code']
    cycles = graph_data['cycles']
    current_period = graph_data['current_period']
    current_level = graph_data['current_level']
    current_start = graph_data['current_start']
    current_end = graph_data['current_end']

    portrait = get_or_create_portrait(current_user.email)
    user_themes = portrait.get('life_themes', [])
    user_tone = portrait.get('tone', '')
    user_email = current_user.email
    user_name = current_user.name or ''

    # Порядок и список блоков — как в ai_life_graph_full.
    block_keys = ['overview', 'current'] + [f'period{i}' for i in range(7)] + ['advice']

    def generate():
        yield format_sse('meta', {
            'code': graph_code,
            'cycles': cycles,
            'current_period': current_period,
            'current_level': current_level,
            'current_start': current_start,
            'current_end': current_end,
        })

        try:
            ai_result = ai_life_graph_full(
                name=user_name,
                birth_date=birth_date,
                cycles=cycles,
                current_level=current_level,
                current_age_start=current_start,
                current_age_end=current_end,
                user_tone=user_tone,
                user_themes=user_themes,
                user_id=user_email,
            )
        except Exception:
            yield format_sse('error', {'message': 'Не удалось сгенерировать разбор'})
            return

        if not ai_result:
            yield format_sse('error', {'message': 'Не удалось сгенерировать разбор'})
            return

        for key in block_keys:
            value = ai_result.get(key)
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

@numerology_bp.route('/api/numerology/life-graph/teaser', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;50 per hour")
def api_life_graph_teaser():
    data = request.json or {}
    birth_date = data.get('birth_date', '')
    if not birth_date:
        return jsonify({"error": "Дата рождения обязательна"}), 400

    graph_data = calculate_life_graph(birth_date)
    if 'error' in graph_data:
        return jsonify({"error": graph_data['error']}), 400
    
    graph_code = graph_data['code']
    cycles = graph_data['cycles']
    current_period = graph_data['current_period']
    current_level = graph_data['current_level']
    current_start = graph_data['current_start']
    current_end = graph_data['current_end']

    ai_result = ai_life_graph_teaser(
        name=data.get('first_name', ''),
        birth_date=birth_date,
        cycles=cycles,
        current_level=current_level,
        current_age_start=current_start,
        current_age_end=current_end,
        user_id=get_identifier()
    )

    if not ai_result:
        return jsonify({"error": "Не удалось сгенерировать тизеры"}), 500

    return jsonify(ai_result)


@numerology_bp.route('/api/numerology/life-graph/suggestions', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;100 per hour")
def api_life_graph_suggestions():
    data = request.json or {}
    full_text = data.get('full_text', '')
    if not full_text:
        return jsonify({"suggestions": [
            "Почему период спада сменяется пиком энергии?",
            "Как использовать текущий период максимально эффективно?",
            "Что делать после завершения пика энергии?"
        ]})
    
    result = ai_life_graph_suggestions(full_text, user_id=get_identifier())
    if result:
        suggestions = [s.strip() for s in result.split('\n') if s.strip()][:3]
    else:
        suggestions = [
            "Почему период спада сменяется пиком энергии?",
            "Как использовать текущий период максимально эффективно?",
            "Что делать после завершения пика энергии?"
        ]
    return jsonify({"suggestions": suggestions})


@numerology_bp.route('/api/numerology/psychomatrix/suggestions', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;100 per hour")
def api_psychomatrix_suggestions():
    data = request.json or {}
    full_text = data.get('full_text', '')
    if not full_text:
        return jsonify({"suggestions": [
            "Почему пустая ячейка характера влияет на жизненные выборы?",
            "Как усилить качество, если в ячейке всего одна цифра?",
            "Что делать, если в психоматрице много пустых ячеек?"
        ]})
    
    result = ai_psychomatrix_suggestions(full_text, user_id=get_identifier())
    if result:
        suggestions = [s.strip() for s in result.split('\n') if s.strip()][:3]
    else:
        suggestions = [
            "Почему пустая ячейка характера влияет на жизненные выборы?",
            "Как усилить качество, если в ячейке всего одна цифра?",
            "Что делать, если в психоматрице много пустых ячеек?"
        ]
    return jsonify({"suggestions": suggestions})