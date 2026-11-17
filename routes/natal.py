# routes/natal.py
from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user
from datetime import datetime

from utils.calculators import calculate_natal_chart, get_moon_phase_full, render_natal_chart_svg
from utils.auth_core import csrf_required
from utils.extensions import limiter
from utils.helpers import get_identifier
from utils.orchestrator import get_or_create_portrait
from utils.ai_service import ai_natal_chart_full, ai_natal_chart_teaser, ai_natal_chart_suggestions
from utils.constants import ELEMENT_MAP, QUALITY_MAP

natal_bp = Blueprint('natal', __name__)

ASPECT_DEFS = [
    ('conjunction', 0, 8, '☌', 'Соединение', 'gold'),
    ('sextile', 60, 6, '⚹', 'Секстиль', 'green'),
    ('square', 90, 6, '□', 'Квадрат', 'red'),
    ('trine', 120, 8, '△', 'Трин', 'green'),
    ('opposition', 180, 8, '☍', 'Оппозиция', 'red'),
]

def _enrich_chart_data(result, birth_date):
    try:
        moon_info = get_moon_phase_full(birth_date, detailed=False)
        result['lunar_day'] = moon_info.get('lunar_day')
        result['lunar_phase'] = moon_info.get('phase_name')
    except:
        result['lunar_day'] = None
        result['lunar_phase'] = None

    all_points = []
    
    def add_point(emoji, name, data):
        if data and data.get('lon'):
            all_points.append({
                'name': name, 'emoji': emoji,
                'lon': data['lon'], 'sign': data.get('sign', '')
            })
    
    add_point('☉', 'Солнце', result.get('sun'))
    add_point('☽', 'Луна', result.get('moon'))
    
    for p_name, p_data in result.get('planets', {}).items():
        add_point(p_data.get('emoji', ''), p_name, p_data)
    
    add_point('☊', 'Сев. узел', result.get('north_node'))
    add_point('☋', 'Юж. узел', result.get('south_node'))
    add_point('⚷', 'Хирон', result.get('chiron'))
    add_point('As', 'Асцендент', result.get('ascendant'))
    add_point('Mc', 'MC', result.get('mc'))

    result['aspects'] = _calc_aspects(all_points)

    elements_count = {'Огонь': 0, 'Земля': 0, 'Воздух': 0, 'Вода': 0}
    qualities_count = {'Кардинальный': 0, 'Фиксированный': 0, 'Мутабельный': 0}

    for p in all_points:
        sign = p.get('sign', '')
        if sign in ELEMENT_MAP:
            elements_count[ELEMENT_MAP[sign]] += 1
        if sign in QUALITY_MAP:
            qualities_count[QUALITY_MAP[sign]] += 1

    total = sum(elements_count.values()) or 1
    result['elements'] = {k: {'count': v, 'percent': round(v / total * 100)} for k, v in elements_count.items()}
    result['qualities'] = {k: {'count': v, 'percent': round(v / total * 100)} for k, v in qualities_count.items()}

    try:
        dt = datetime.strptime(birth_date, '%Y-%m-%d')
        days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        result['weekday'] = days[dt.weekday()]
    except:
        result['weekday'] = None

    fixed_stars = [
        ('Альтаир', 301.78, 'Смелость, риск, быстрые решения'),
        ('Альдебаран', 69.79, 'Успех, энергия, воинский дух'),
        ('Антарес', 249.76, 'Страсть, настойчивость, трансформация'),
        ('Бетельгейзе', 88.79, 'Слава, удача, военные почести'),
        ('Вега', 285.28, 'Харизма, артистизм, популярность'),
        ('Денеб', 49.88, 'Идеализм, вдохновение, лидерство'),
        ('Капелла', 81.73, 'Независимость, богатство, почести'),
        ('Кастор', 110.24, 'Острый ум, интеллект, оккультные способности'),
        ('Поллукс', 113.22, 'Храбрость, защита, победа'),
        ('Процион', 85.24, 'Удача в делах, богатство, слава'),
        ('Регул', 149.83, 'Власть, успех, лидерство'),
        ('Ригель', 76.85, 'Слава, богатство, изобретательность'),
        ('Сириус', 104.05, 'Амбиции, успех, преданность'),
        ('Спика', 203.84, 'Талант, знания, защита'),
        ('Фомальгаут', 333.63, 'Духовность, идеализм, мечты'),
    ]
    
    result['fixed_stars'] = []
    
    star_points = []
    def add_star_point(name, data):
        if data and data.get('lon') is not None:
            star_points.append({'name': name, 'lon': data['lon']})
    
    add_star_point('Солнце', result.get('sun'))
    add_star_point('Луна', result.get('moon'))
    add_star_point('Асцендент', result.get('ascendant'))
    add_star_point('MC', result.get('mc'))
    for p_name, p_data in result.get('planets', {}).items():
        add_star_point(p_name, p_data)
    
    for star_name, star_lon, star_meaning in fixed_stars:
        for point in star_points:
            orbis = abs(point['lon'] - star_lon)
            if orbis > 180:
                orbis = 360 - orbis
            if orbis <= 1.0:
                result['fixed_stars'].append({
                    'planet': point['name'],
                    'star': star_name,
                    'orbis': round(orbis, 2),
                    'meaning': star_meaning
                })
    
    result['fixed_stars'].sort(key=lambda x: x['orbis'])

    result['chart_svg'] = render_natal_chart_svg(result)


def _calc_aspects(points_list):
    aspects = []
    
    for i in range(len(points_list)):
        for j in range(i + 1, len(points_list)):
            if (points_list[i]['name'] == 'Сев. узел' and points_list[j]['name'] == 'Юж. узел') or \
               (points_list[i]['name'] == 'Юж. узел' and points_list[j]['name'] == 'Сев. узел'):
                continue

            a_lon = points_list[i]['lon']
            b_lon = points_list[j]['lon']
            diff = abs(a_lon - b_lon) % 360
            diff = min(diff, 360 - diff)

            for name, angle, orb, symbol, name_ru, color in ASPECT_DEFS:
                if abs(diff - angle) <= orb:
                    direction = 'сходящийся' if diff <= angle else 'расходящийся'
                    aspects.append({
                        'planet1': points_list[i]['name'],
                        'planet1_emoji': points_list[i]['emoji'] if points_list[i]['emoji'] not in ('As', 'Mc') else '',
                        'planet2': points_list[j]['name'],
                        'planet2_emoji': points_list[j]['emoji'] if points_list[j]['emoji'] not in ('As', 'Mc') else '',
                        'aspect': name,
                        'symbol': symbol,
                        'name_ru': name_ru,
                        'orbis': round(abs(diff - angle), 2),
                        'direction': direction,
                        'color': color
                    })
                    break

    return sorted(aspects, key=lambda x: x['orbis'])


@natal_bp.route('/natal-chart')
def natal_chart_page():
    return render_template('natal_chart.html')


@natal_bp.route('/api/natal-chart', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;100 per hour")
def api_natal_chart():
    data = request.json or {}
    birth_date = data.get('birth_date', '')
    birth_time = data.get('birth_time', '12:00')
    birth_place = data.get('birth_place', '')
    # Координаты, если фронт уже получил их через автокомплит города
    _lat = data.get('lat') or None
    _lng = data.get('lng') or None
    try:
        _lat = float(_lat) if _lat else None
        _lng = float(_lng) if _lng else None
    except (ValueError, TypeError):
        _lat = _lng = None

    result = calculate_natal_chart(birth_date, birth_time, birth_place, lat=_lat, lng=_lng)

    if result.get('success'):
        _enrich_chart_data(result, birth_date)

        if current_user.is_authenticated and current_user.subscription == 'Пламя':
            result['is_premium'] = True
        else:
            result['is_premium'] = False
            teaser = ai_natal_chart_teaser(
                name=current_user.name if current_user.is_authenticated else '',
                birth_date=birth_date,
                sun=result.get('sun', {}),
                moon=result.get('moon', {}),
                ascendant=result.get('ascendant', {}),
                user_id=get_identifier()
            )
            if teaser:
                result['teaser'] = teaser

    return jsonify(result)


@natal_bp.route('/api/natal-chart/ai-full', methods=['POST'])
@csrf_required
@limiter.limit("5 per minute;30 per hour")
def api_natal_chart_ai_full():
    if not current_user.is_authenticated or current_user.subscription != 'Пламя':
        return jsonify({"error": "Доступно на тарифе Пламя"}), 402

    data = request.json or {}
    birth_date = data.get('birth_date', '')
    birth_time = data.get('birth_time', '12:00')
    birth_place = data.get('birth_place', '')
    _lat = data.get('lat') or None
    _lng = data.get('lng') or None
    try:
        _lat = float(_lat) if _lat else None
        _lng = float(_lng) if _lng else None
    except (ValueError, TypeError):
        _lat = _lng = None

    if not birth_date:
        return jsonify({"error": "Дата рождения обязательна"}), 400

    result = calculate_natal_chart(birth_date, birth_time, birth_place, lat=_lat, lng=_lng)

    if not result.get('success'):
        return jsonify({"error": "Не удалось построить карту"}), 500

    _enrich_chart_data(result, birth_date)

    portrait = get_or_create_portrait(current_user.email)
    user_themes = portrait.get('life_themes', [])
    user_tone = portrait.get('tone', '')

    ai_result = ai_natal_chart_full(
        name=current_user.name or '',
        birth_date=birth_date,
        birth_time=birth_time,
        birth_place=birth_place,
        sun=result.get('sun', {}),
        moon=result.get('moon', {}),
        ascendant=result.get('ascendant', {}),
        planets=result.get('planets', {}),
        houses=result.get('houses', []),
        user_tone=user_tone,
        user_themes=user_themes,
        user_id=current_user.email
    )

    if not ai_result:
        return jsonify({"error": "Не удалось сгенерировать разбор"}), 500

    ai_result['chart_data'] = {
        'sun': result.get('sun'),
        'moon': result.get('moon'),
        'ascendant': result.get('ascendant'),
        'mc': result.get('mc'),
        'planets': result.get('planets'),
        'houses': result.get('houses'),
        'north_node': result.get('north_node'),
        'south_node': result.get('south_node'),
        'chiron': result.get('chiron'),
        'birth_date': birth_date,
        'birth_time': birth_time,
        'birth_place': birth_place
    }
    ai_result['chart_svg'] = result.get('chart_svg')
    ai_result['elements'] = result.get('elements')
    ai_result['qualities'] = result.get('qualities')
    ai_result['aspects'] = result.get('aspects')
    ai_result['lunar_day'] = result.get('lunar_day')
    ai_result['lunar_phase'] = result.get('lunar_phase')
    ai_result['weekday'] = result.get('weekday')
    ai_result['lat'] = result.get('lat')
    ai_result['lng'] = result.get('lng')
    ai_result['success'] = True

    return jsonify(ai_result)

@natal_bp.route('/api/natal-chart/ai-full/stream', methods=['POST'])
@csrf_required
@limiter.limit("5 per minute;30 per hour")
def api_natal_chart_ai_full_stream():
    """
    SSE-стрим разбора натальной карты (только Пламя).

    Контракт:
        event: meta  → {
            birth_date, birth_time, birth_place, lat, lng, weekday,
            chart_data: {sun, moon, ascendant, mc, planets, houses,
                         north_node, south_node, chiron,
                         birth_date, birth_time, birth_place},
            chart_svg, elements, qualities, aspects,
            fixed_stars, lunar_day, lunar_phase
        }
        event: block → {name, value}
            name: sun, moon, ascendant, planets, houses,
                  summary, strengths, challenges, advice
            value = строка (AI-разбор соответствующего поля)
        event: done  → {success: True}
        event: error → {message}

    Расчёт карты, обогащение, промпт — идентичны api_natal_chart_ai_full.
    Отличие только в транспорте: meta сразу (SVG-колесо + планеты + дома +
    аспекты), AI-разбор — по блокам после получения JSON.
    """
    from flask import Response, stream_with_context
    from utils.stream_helpers import format_sse

    if not current_user.is_authenticated or current_user.subscription != 'Пламя':
        return jsonify({"error": "Доступно на тарифе Пламя"}), 402

    data = request.json or {}
    birth_date = data.get('birth_date', '')
    birth_time = data.get('birth_time', '12:00')
    birth_place = data.get('birth_place', '')
    _lat = data.get('lat') or None
    _lng = data.get('lng') or None
    try:
        _lat = float(_lat) if _lat else None
        _lng = float(_lng) if _lng else None
    except (ValueError, TypeError):
        _lat = _lng = None

    if not birth_date:
        return jsonify({"error": "Дата рождения обязательна"}), 400

    # Расчёт карты — без AI.
    result = calculate_natal_chart(birth_date, birth_time, birth_place, lat=_lat, lng=_lng)
    if not result.get('success'):
        return jsonify({"error": "Не удалось построить карту"}), 500

    _enrich_chart_data(result, birth_date)

    # Контекст пользователя — до генератора.
    portrait = get_or_create_portrait(current_user.email)
    user_themes = portrait.get('life_themes', [])
    user_tone = portrait.get('tone', '')
    user_name = current_user.name or ''
    user_email = current_user.email

    # Поля JSON, которые придут от ai_natal_chart_full. Порядок фиксирован.
    block_keys = ['sun', 'moon', 'ascendant', 'planets', 'houses',
                  'summary', 'strengths', 'challenges', 'advice']

    # Соберём meta одним разом: всё, что нужно фронту для отрисовки
    # SVG-колеса, таблиц планет, сетки домов, аспектов, стихий, звёзд.
    # AI-поля (sun, moon, ...) — НЕ в meta, они перезапишут эти же ключи,
    # поэтому meta хранит их под chart_data.
    meta_chart_data = {
        'sun': result.get('sun'),
        'moon': result.get('moon'),
        'ascendant': result.get('ascendant'),
        'mc': result.get('mc'),
        'planets': result.get('planets'),
        'houses': result.get('houses'),
        'north_node': result.get('north_node'),
        'south_node': result.get('south_node'),
        'chiron': result.get('chiron'),
        'birth_date': birth_date,
        'birth_time': birth_time,
        'birth_place': birth_place,
    }

    meta_payload = {
        'birth_date': birth_date,
        'birth_time': birth_time,
        'birth_place': birth_place,
        'lat': result.get('lat'),
        'lng': result.get('lng'),
        'weekday': result.get('weekday'),
        'chart_data': meta_chart_data,
        'chart_svg': result.get('chart_svg'),
        'elements': result.get('elements'),
        'qualities': result.get('qualities'),
        'aspects': result.get('aspects'),
        'fixed_stars': result.get('fixed_stars'),
        'lunar_day': result.get('lunar_day'),
        'lunar_phase': result.get('lunar_phase'),
    }

    def generate():
        yield format_sse('meta', meta_payload)

        try:
            ai_result = ai_natal_chart_full(
                name=user_name,
                birth_date=birth_date,
                birth_time=birth_time,
                birth_place=birth_place,
                sun=result.get('sun', {}),
                moon=result.get('moon', {}),
                ascendant=result.get('ascendant', {}),
                planets=result.get('planets', {}),
                houses=result.get('houses', []),
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

        yield format_sse('done', {'success': True})

    headers = {
        'Cache-Control': 'no-cache, no-transform',
        'X-Accel-Buffering': 'no',
    }
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers=headers,
    )

@natal_bp.route('/api/natal-chart/suggestions', methods=['POST'])
@csrf_required
@limiter.limit("10 per minute;100 per hour")
def api_natal_chart_suggestions():
    data = request.json or {}
    full_text = data.get('full_text', '')
    
    if not full_text:
        return jsonify({"suggestions": [
            "Что означает Солнце в этом знаке?",
            "Как Луна влияет на эмоциональную сферу?",
            "Почему Асцендент важен для первого впечатления?"
        ]})

    result = ai_natal_chart_suggestions(full_text, user_id=get_identifier())
    
    if result:
        suggestions = [s.strip() for s in result.split('\n') if s.strip()][:3]
    else:
        suggestions = [
            "Что означает Солнце в этом знаке?",
            "Как Луна влияет на эмоциональную сферу?",
            "Почему Асцендент важен для первого впечатления?"
        ]
    return jsonify({"suggestions": suggestions})