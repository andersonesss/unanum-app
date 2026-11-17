from flask import Flask, render_template, request, jsonify, redirect, session, Response, stream_with_context
from flask_login import current_user
import json
import os
import uuid
import hmac
from dotenv import load_dotenv
from datetime import timedelta
from functools import wraps

from werkzeug.exceptions import HTTPException

from database.db import USE_POSTGRES, init_db, get_db, add_log
from config import Config

load_dotenv()

# Создаём папку для логов Gunicorn (нужна при запуске через gunicorn_config.py)
os.makedirs('logs', exist_ok=True)

init_db()

# Разрешённые MIME-типы для загрузки изображений (админка)
ALLOWED_IMAGE_MIME = {'image/png', 'image/jpeg', 'image/webp', 'image/gif'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


def seed_share_defaults():
    """Создаёт дефолтные элементы шаринга, если их нет.
    Проверяет КАЖДЫЙ элемент отдельно через SELECT перед INSERT — иначе
    при частичном отсутствии дефолтов в PG создавались бы дубликаты
    (в этих таблицах нет UNIQUE(name), а ON CONFLICT DO NOTHING без колонок
    в такой ситуации вставляет новую строку)."""
    from PIL import Image, ImageDraw, ImageFont

    share_dir = os.path.join('static', 'images', 'share')
    os.makedirs(share_dir, exist_ok=True)

    bg_name = 'Тёмно-зелёный градиент'
    bg_image_path = '/static/images/share/default_bg.png'
    wm_name = 'Numer'
    wm_image_path = '/static/images/share/numer_watermark.png'
    st_name = 'Золотой центр'
    tpl_name = 'Дефолтный'

    with get_db() as conn:
        cur = conn.cursor() if USE_POSTGRES else conn.cursor()

        # ---------- 1. Фон ----------
        if USE_POSTGRES:
            cur.execute("SELECT id FROM share_backgrounds WHERE name = %s LIMIT 1", (bg_name,))
        else:
            cur.execute("SELECT id FROM share_backgrounds WHERE name = ? LIMIT 1", (bg_name,))
        bg_row = cur.fetchone()
        bg_id = bg_row['id'] if bg_row else None

        if bg_id is None:
            # Файл фона создаём, только если его нет
            bg_file = os.path.join(share_dir, 'default_bg.png')
            if not os.path.exists(bg_file):
                bg_img = Image.new('RGB', (1080, 1920), (10, 26, 10))
                draw = ImageDraw.Draw(bg_img)
                for i in range(1920):
                    r = 10 + int((i / 1920) * 20)
                    g = 26 + int((i / 1920) * 30)
                    b = 10 + int((i / 1920) * 10)
                    draw.line([(0, i), (1080, i)], fill=(r, g, b))
                bg_img.save(bg_file)

            if USE_POSTGRES:
                cur.execute(
                    "INSERT INTO share_backgrounds (name, image_path, tariff, is_active) "
                    "VALUES (%s, %s, %s, 1) RETURNING id",
                    (bg_name, bg_image_path, 'Искра')
                )
                bg_id = cur.fetchone()['id']
            else:
                cur.execute(
                    "INSERT INTO share_backgrounds (name, image_path, tariff, is_active) "
                    "VALUES (?, ?, ?, 1)",
                    (bg_name, bg_image_path, 'Искра')
                )
                bg_id = cur.lastrowid

        # ---------- 2. Водяной знак ----------
        if USE_POSTGRES:
            cur.execute("SELECT id FROM share_watermarks WHERE name = %s LIMIT 1", (wm_name,))
        else:
            cur.execute("SELECT id FROM share_watermarks WHERE name = ? LIMIT 1", (wm_name,))
        wm_row = cur.fetchone()
        wm_id = wm_row['id'] if wm_row else None

        if wm_id is None:
            wm_file = os.path.join(share_dir, 'numer_watermark.png')
            if not os.path.exists(wm_file):
                wm_img = Image.new('RGBA', (200, 60), (0, 0, 0, 0))
                draw = ImageDraw.Draw(wm_img)
                try:
                    font = ImageFont.truetype(os.path.join('static', 'fonts', 'Roboto-Regular.ttf'), 24)
                except Exception:
                    font = ImageFont.load_default()
                draw.text((10, 15), 'unanum', fill=(255, 213, 79, 180), font=font)
                wm_img.save(wm_file)

            if USE_POSTGRES:
                cur.execute(
                    "INSERT INTO share_watermarks (name, image_path, position, size, tariff, is_active) "
                    "VALUES (%s, %s, %s, %s, %s, 1) RETURNING id",
                    (wm_name, wm_image_path, 'bottom-right', '200x60', 'Искра')
                )
                wm_id = cur.fetchone()['id']
            else:
                cur.execute(
                    "INSERT INTO share_watermarks (name, image_path, position, size, tariff, is_active) "
                    "VALUES (?, ?, ?, ?, ?, 1)",
                    (wm_name, wm_image_path, 'bottom-right', '200x60', 'Искра')
                )
                wm_id = cur.lastrowid

        # ---------- 3. Текстовый стиль ----------
        if USE_POSTGRES:
            cur.execute("SELECT id FROM share_text_styles WHERE name = %s LIMIT 1", (st_name,))
        else:
            cur.execute("SELECT id FROM share_text_styles WHERE name = ? LIMIT 1", (st_name,))
        st_row = cur.fetchone()
        st_id = st_row['id'] if st_row else None

        if st_id is None:
            if USE_POSTGRES:
                cur.execute(
                    "INSERT INTO share_text_styles "
                    "(name, color, align, shadow_color, shadow_offset, shadow_blur, "
                    " font_size_min, font_size_max, tariff, is_active) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1) RETURNING id",
                    (st_name, '#ffd54f', 'center', '#000000', '2,2', 4, 32, 60, 'Искра')
                )
                st_id = cur.fetchone()['id']
            else:
                cur.execute(
                    "INSERT INTO share_text_styles "
                    "(name, color, align, shadow_color, shadow_offset, shadow_blur, "
                    " font_size_min, font_size_max, tariff, is_active) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                    (st_name, '#ffd54f', 'center', '#000000', '2,2', 4, 32, 60, 'Искра')
                )
                st_id = cur.lastrowid

        # ---------- 4. Шаблон ----------
        if USE_POSTGRES:
            cur.execute(
                "SELECT id FROM share_templates WHERE name = %s AND is_default = 1 LIMIT 1",
                (tpl_name,)
            )
        else:
            cur.execute(
                "SELECT id FROM share_templates WHERE name = ? AND is_default = 1 LIMIT 1",
                (tpl_name,)
            )
        tpl_row = cur.fetchone()

        if tpl_row is None:
            if USE_POSTGRES:
                cur.execute(
                    "INSERT INTO share_templates "
                    "(name, background_id, text_style_id, watermark_id, is_default, tariff, is_active) "
                    "VALUES (%s, %s, %s, %s, 1, %s, 1)",
                    (tpl_name, bg_id, st_id, wm_id, 'Искра')
                )
            else:
                cur.execute(
                    "INSERT INTO share_templates "
                    "(name, background_id, text_style_id, watermark_id, is_default, tariff, is_active) "
                    "VALUES (?, ?, ?, ?, 1, ?, 1)",
                    (tpl_name, bg_id, st_id, wm_id, 'Искра')
                )

        conn.commit()
        print("[OK] Дефолтные элементы шаринга проверены/созданы")

# Вызвать после init_db()
seed_share_defaults()

from utils.tarot import (
    get_daily_card,
    do_spread,
    search_cards,
    get_card_detail,
    get_card_by_id
)
from utils.ai_service import clear_ai_cache
from utils.orchestrator import (
    handle_dialogue,
    generate_follow_up_questions,
    update_portrait_from_init,
    get_or_create_portrait
)

# ---------- Вспомогательные функции перенесены в utils/helpers.py ----------
from utils.helpers import get_identifier, today_msk

# ---------- Объекты аутентификации перенесены в utils/auth_core.py ----------
from utils.auth_core import login_manager, generate_csrf_token, csrf_required
from utils.image_pool import run_image_job

# ---------- Flask ----------
app = Flask(__name__)

# ProxyFix — корректное чтение X-Forwarded-For / -Proto / -Host за Nginx.
# Без него request.remote_addr всегда 127.0.0.1, что ломает привязку админ-сессии к IP.
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB — защита от больших загрузок
app.secret_key = Config.SECRET_KEY
if not app.secret_key:
    raise RuntimeError("SECRET_KEY environment variable is not set")
if len(app.secret_key) < 32:
    raise RuntimeError("SECRET_KEY must be at least 32 characters long")

# ---------- Безопасность cookies ----------
# HttpOnly — JS не может читать cookie (защита от XSS-кражи сессии)
# SameSite=Lax — cookie не отправляется на cross-site POST (защита от CSRF)
# Secure — cookie только по HTTPS (включаем в production)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'

# ---------- Flask-Login ----------
login_manager.init_app(app)

# ---------- Flask-Limiter ----------
from utils.extensions import limiter
limiter.init_app(app)

# ---------- CSRF (глобальная переменная шаблона) ----------
app.jinja_env.globals['csrf_token'] = generate_csrf_token

# ---------- Админ ----------
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_authenticated'):
            return jsonify({"error": "unauthorized"}), 403
        # Проверка IP — админская сессия привязана к IP при логине
        login_ip = session.get('admin_ip')
        if login_ip and login_ip != request.remote_addr:
            session.pop('admin_authenticated', None)
            return jsonify({"error": "session expired"}), 403
        return f(*args, **kwargs)
    return decorated

# ---------- Blueprints ----------
from routes.auth import auth_bp
from routes.moon import moon_bp
from routes.financial import financial_bp
from routes.horoscope import horoscope_bp
from routes.numerology import numerology_bp
from routes.natal import natal_bp
from routes.compatibility import compatibility_bp

app.register_blueprint(auth_bp)
app.register_blueprint(moon_bp)
app.register_blueprint(financial_bp)
app.register_blueprint(horoscope_bp)
app.register_blueprint(numerology_bp)
app.register_blueprint(natal_bp)
app.register_blueprint(compatibility_bp)

# ---------- Глобальные переменные для шаблонов ----------
@app.context_processor
def inject_global_config():
    """Пробрасывает общие константы во все шаблоны Jinja2."""
    return {
        'PAYWALL_PRICE_RUB': Config.PAYWALL_PRICE_RUB,
    }

# ========== SEO ==========
@app.route('/robots.txt')
def robots_txt():
    return app.send_static_file('robots.txt')

@app.route('/sitemap.xml')
def sitemap_xml():
    return app.send_static_file('sitemap.xml')

# ========== Tarot API ==========
@app.route('/api/tarot/daily', methods=['POST'])
@csrf_required
@limiter.limit("20 per minute;200 per hour")
def api_tarot_daily():
    identifier = get_identifier()
    result = get_daily_card(
        identifier=identifier,
        use_ai=True,
        user_email=current_user.email if current_user.is_authenticated else None,
        user_subscription=current_user.subscription if current_user.is_authenticated else 'Искра'
    )
    return jsonify(result)

@app.route('/api/tarot/daily/stream', methods=['POST'])
@csrf_required
@limiter.limit("20 per minute;200 per hour")
def api_tarot_daily_stream():
    """
    SSE-стрим карты дня.

    Контракт:
        event: meta  → {id, name, name_en, is_reversed, meaning, advice, date, cached, ...}
        event: chunk → {chunk: '...'}
        event: done  → {full_text: '...', is_reversed: bool}
        event: error → {message}
    """
    from flask import Response, stream_with_context
    from utils.tarot import get_daily_card_stream
    from utils.stream_helpers import format_sse

    # Всё захватываем ДО генератора.
    identifier = get_identifier()
    user_email = current_user.email if current_user.is_authenticated else None
    user_subscription = current_user.subscription if current_user.is_authenticated else 'Искра'

    def generate():
        try:
            for event_type, event_data in get_daily_card_stream(
                identifier=identifier,
                user_email=user_email,
                user_subscription=user_subscription,
            ):
                yield format_sse(event_type, event_data)
        except Exception:
            yield format_sse('error', {'message': 'Что-то пошло не так. Попробуйте ещё раз.'})

    headers = {
        'Cache-Control': 'no-cache, no-transform',
        'X-Accel-Buffering': 'no',
    }
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers=headers,
    )

@app.route('/api/tarot/spread', methods=['POST'])
@csrf_required
@limiter.limit("3 per minute;10 per hour")
def api_tarot_spread():
    data = request.json or {}
    spread_type = data.get('type', 'one_card')
    question = data.get('question', '')
    # ВАЖНО: current_user.subscription доступен только у аутентифицированного User
    # (в auth_core.py User.__init__ задаёт self.subscription).
    # AnonymousUserMixin от Flask-Login такого атрибута НЕ имеет → AttributeError.
    # Поэтому сначала проверяем is_authenticated.
    use_ai = current_user.is_authenticated and current_user.subscription == 'Пламя'
    identifier = get_identifier()

    if not current_user.is_authenticated:
        with get_db() as conn:
            if USE_POSTGRES:
                # PostgreSQL: атомарный INSERT ... ON CONFLICT + UPDATE с RETURNING
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO trial_tokens (identifier, spreads_used, max_spreads)
                    VALUES (%s, 1, 1)
                    ON CONFLICT (identifier) DO UPDATE
                    SET spreads_used = trial_tokens.spreads_used + 1
                    WHERE trial_tokens.spreads_used < trial_tokens.max_spreads
                    RETURNING spreads_used, max_spreads
                """, (identifier,))
                row = cur.fetchone()
                if row is None:
                    # Не обновилось — лимит исчерпан
                    conn.rollback()
                    return jsonify({
                        "error": "trial_limit",
                        "message": "Ты уже использовала пробный расклад. Зарегистрируйся для новых."
                    }), 402
                conn.commit()
            else:
                # SQLite: старая логика с BEGIN IMMEDIATE
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT * FROM trial_tokens WHERE identifier = ?", (identifier,)
                ).fetchone()
                if not row:
                    conn.execute(
                        "INSERT INTO trial_tokens (identifier, spreads_used, max_spreads) VALUES (?, 1, 1)",
                        (identifier,)
                    )
                    conn.commit()
                else:
                    if row['spreads_used'] >= row['max_spreads']:
                        conn.rollback()
                        return jsonify({
                            "error": "trial_limit",
                            "message": "Ты уже использовала пробный расклад. Зарегистрируйся для новых."
                        }), 402
                    conn.execute(
                        "UPDATE trial_tokens SET spreads_used = spreads_used + 1 WHERE identifier = ? AND spreads_used < max_spreads",
                        (identifier,)
                    )
                    if conn.total_changes == 0:
                        conn.rollback()
                        return jsonify({
                            "error": "trial_limit",
                            "message": "Лимит пробных раскладов исчерпан."
                        }), 402
                    conn.commit()

    result = do_spread(spread_type, question, identifier=identifier, use_ai=use_ai)
    return jsonify(result)

@app.route('/api/tarot/spread/stream', methods=['POST'])
@csrf_required
@limiter.limit("3 per minute;10 per hour")
def api_tarot_spread_stream():
    """
    SSE-стрим расклада Таро.

    Контракт:
        event: meta  → {type, question, cards, date}
        event: chunk → {chunk: '...'}          (только если use_ai=True)
        event: done  → {ai_interpretation: '...'}
        event: error → {message}

    Проверка trial-лимита для неавторизованного гостя — дублирует логику
    /api/tarot/spread. TODO: вынести в _check_trial_limit при унификации.
    """
    from flask import Response, stream_with_context
    from utils.tarot import do_spread_stream
    from utils.stream_helpers import format_sse

    data = request.json or {}
    spread_type = data.get('type', 'one_card')
    question = data.get('question', '')

    use_ai = current_user.is_authenticated and current_user.subscription == 'Пламя'
    identifier = get_identifier()

    # Проверка trial-лимита — как в /api/tarot/spread.
    if not current_user.is_authenticated:
        with get_db() as conn:
            if USE_POSTGRES:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO trial_tokens (identifier, spreads_used, max_spreads)
                    VALUES (%s, 1, 1)
                    ON CONFLICT (identifier) DO UPDATE
                    SET spreads_used = trial_tokens.spreads_used + 1
                    WHERE trial_tokens.spreads_used < trial_tokens.max_spreads
                    RETURNING spreads_used, max_spreads
                """, (identifier,))
                row = cur.fetchone()
                if row is None:
                    conn.rollback()
                    return jsonify({
                        "error": "trial_limit",
                        "message": "Ты уже использовала пробный расклад. Зарегистрируйся для новых."
                    }), 402
                conn.commit()
            else:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT * FROM trial_tokens WHERE identifier = ?", (identifier,)
                ).fetchone()
                if not row:
                    conn.execute(
                        "INSERT INTO trial_tokens (identifier, spreads_used, max_spreads) VALUES (?, 1, 1)",
                        (identifier,)
                    )
                    conn.commit()
                else:
                    if row['spreads_used'] >= row['max_spreads']:
                        conn.rollback()
                        return jsonify({
                            "error": "trial_limit",
                            "message": "Ты уже использовала пробный расклад. Зарегистрируйся для новых."
                        }), 402
                    conn.execute(
                        "UPDATE trial_tokens SET spreads_used = spreads_used + 1 "
                        "WHERE identifier = ? AND spreads_used < max_spreads",
                        (identifier,)
                    )
                    if conn.total_changes == 0:
                        conn.rollback()
                        return jsonify({
                            "error": "trial_limit",
                            "message": "Лимит пробных раскладов исчерпан."
                        }), 402
                    conn.commit()

    def generate():
        try:
            for event_type, event_data in do_spread_stream(
                spread_type=spread_type,
                question=question,
                identifier=identifier,
                use_ai=use_ai,
            ):
                yield format_sse(event_type, event_data)
        except Exception:
            yield format_sse('error', {'message': 'Что-то пошло не так. Попробуйте ещё раз.'})

    headers = {
        'Cache-Control': 'no-cache, no-transform',
        'X-Accel-Buffering': 'no',
    }
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers=headers,
    )

@app.route('/api/tarot/library', methods=['GET'])
def api_tarot_library():
    query = request.args.get('q', '')
    arcana = request.args.get('arcana', 'all')
    suit = request.args.get('suit', 'all')
    sort = request.args.get('sort', 'number')
    result = search_cards(query, arcana, suit, sort)
    return jsonify(result)

@app.route('/api/tarot/card/<int:card_id>', methods=['GET'])
def api_tarot_card_detail(card_id):
    result = get_card_detail(card_id)
    return jsonify(result)

@app.route('/api/tarot/daily/history', methods=['GET'])
def api_daily_history():
    identifier = get_identifier()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_cards WHERE identifier = ? ORDER BY card_date DESC LIMIT 30",
            (identifier,)
        ).fetchall()
        history = []
        for row in rows:
            card = get_card_by_id(row['card_id'])
            if card:
                history.append({
                    "date": row['card_date'],
                    "card_id": row['card_id'],
                    "name_ru": card['name_ru'],
                    "is_reversed": bool(row['is_reversed']),
                    "meaning": card['meaning_reversed'] if row['is_reversed'] else card['meaning_upright'],
                })
        return jsonify(history)

# ========== unanum Dialogue API ==========

def _check_daily_question_limit():
    """Проверяет дневной лимит вопросов к unanum.
    Возвращает None, если можно задавать вопросы, или кортеж (jsonify-ответ, HTTP-код)."""
    if current_user.is_authenticated:
        if current_user.subscription == 'Пламя':
            return None
        user_id = current_user.email
        daily_limit = 3
    else:
        user_id = get_identifier()
        daily_limit = 1

    with get_db() as conn:
        if USE_POSTGRES:
            # Диапазон МСК-суток в timestamptz: [начало МСК, конец МСК).
            # PG использует индекс по created_at, если сравнивать с диапазоном,
            # а не с вычисляемым выражением (created_at AT TIME ZONE ...)::date.
            from datetime import datetime as _dt, timedelta as _td
            _today_msk = today_msk()
            _start_msk = _dt.strptime(_today_msk, '%Y-%m-%d')
            _end_msk = _start_msk + _td(days=1)
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM numer_memory "
                "WHERE user_id = ? AND type = 'dialogue' "
                "AND created_at >= ?::timestamptz AT TIME ZONE 'Europe/Moscow' "
                "AND created_at <  ?::timestamptz AT TIME ZONE 'Europe/Moscow'",
                (user_id, _start_msk.isoformat(), _end_msk.isoformat())
            ).fetchone()
        else:
            # SQLite: created_at — UTC-строка. Диапазон [начало МСК, конец МСК) в UTC.
            # МСК = UTC+3 (без перехода на летнее время с 2014).
            # BETWEEN позволяет SQLite использовать индекс по created_at.
            from datetime import datetime as _dt, timedelta as _td
            _today_msk = today_msk()
            _start_utc = (_dt.strptime(_today_msk, '%Y-%m-%d') - _td(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
            _end_utc = (_dt.strptime(_today_msk, '%Y-%m-%d') + _td(days=1) - _td(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM numer_memory "
                "WHERE user_id = ? AND type = 'dialogue' "
                "AND created_at >= ? AND created_at < ?",
                (user_id, _start_utc, _end_utc)
            ).fetchone()
        count = row['cnt'] if row else 0

    if count >= daily_limit:
        return jsonify({
            "error": "limit_exceeded",
            "message": f"Дневной лимит вопросов исчерпан ({daily_limit} в день). Оформите тариф Пламя для безлимита."
        }), 402
    return None


@app.route('/api/numer/init', methods=['POST'])
@csrf_required
def api_numer_init():
    data = request.json or {}
    identifier = get_identifier()
    
    init_data = {
        'name': data.get('name', ''),
        'birth_date': data.get('birth_date', ''),
        'birth_time': data.get('birth_time', '12:00'),
        'birth_place': data.get('birth_place', ''),
        'life_themes': data.get('life_themes', []),
        'tone': data.get('tone', ''),
        'coping': data.get('coping', ''),
    }
    
    portrait = update_portrait_from_init(identifier, init_data)
    
    name = portrait.get('name', '')
    greeting = f"Добро пожаловать{', ' + name if name else ''}. Я unanum. "
    
    if portrait.get('natal_chart'):
        sun = portrait['natal_chart'].get('sun', {})
        asc = portrait['natal_chart'].get('ascendant', {})
        if sun and asc:
            greeting += f"Твоё Солнце в {sun.get('sign', '?')}, асцендент в {asc.get('sign', '?')}. "
        greeting += "Теперь я могу говорить с тобой лично. Хочешь вытянуть карту дня или просто расскажи, что тебя волнует?"
    else:
        greeting += "Расскажи, что тебя волнует — и я помогу тебе разобраться."
    
    questions = generate_follow_up_questions(identifier, 'general')
    
    return jsonify({
        "success": True,
        "greeting": greeting,
        "follow_up_questions": questions,
        "portrait": portrait
    })

@app.route('/api/numer/dialogue', methods=['POST'])
@csrf_required
@limiter.limit("15 per minute;150 per hour")
def api_numer_dialogue():
    data = request.json or {}
    message = data.get('message', '').strip()
    section = data.get('section', 'general')
    context = data.get('context', {})
    
    if not message:
        return jsonify({"error": "Пустое сообщение"}), 400
    
    limit_check = _check_daily_question_limit()
    if limit_check:
        return limit_check
    
    identifier = get_identifier()
    result = handle_dialogue(identifier, message, section, context)
    
    questions = generate_follow_up_questions(identifier, section)
    result['follow_up_questions'] = questions
    
    return jsonify(result)

@app.route('/api/numer/portrait', methods=['GET'])
def api_numer_portrait():
    identifier = get_identifier()
    portrait = get_or_create_portrait(identifier)
    return jsonify(portrait)

@app.route('/api/numer/memory', methods=['GET'])
def api_numer_memory():
    identifier = get_identifier()
    try:
        limit = int(request.args.get('limit', 30))
        limit = max(1, min(limit, 200))  # от 1 до 200
    except (ValueError, TypeError):
        limit = 30
    offset = request.args.get('offset', 0, type=int)
    filter_type = request.args.get('type', '')
    search = request.args.get('search', '').strip()
    
    with get_db() as conn:
        query = """SELECT type, content, metadata, created_at 
                   FROM numer_memory 
                   WHERE user_id = ?"""
        params = [identifier]
        
        if filter_type:
            query += " AND type = ?"
            params.append(filter_type)
        
        if search:
            query += " AND content LIKE ?"
            params.append(f'%{search}%')
        
        # Всего записей (для статистики)
        count_row = conn.execute(
            "SELECT COUNT(*) as total FROM numer_memory WHERE user_id = ?",
            (identifier,)
        ).fetchone()
        total_count = count_row['total'] if count_row else 0
        
        # За сегодня (MSK). Диапазонное сравнение позволяет использовать индекс по created_at.
        today = today_msk()
        if USE_POSTGRES:
            from datetime import datetime as _dt, timedelta as _td
            _start_msk = _dt.strptime(today, '%Y-%m-%d')
            _end_msk = _start_msk + _td(days=1)
            today_count = conn.execute(
                "SELECT COUNT(*) as total FROM numer_memory "
                "WHERE user_id = ? "
                "AND created_at >= ?::timestamptz AT TIME ZONE 'Europe/Moscow' "
                "AND created_at <  ?::timestamptz AT TIME ZONE 'Europe/Moscow'",
                (identifier, _start_msk.isoformat(), _end_msk.isoformat())
            ).fetchone()['total']
        else:
            from datetime import datetime as _dt, timedelta as _td
            _start_utc = (_dt.strptime(today, '%Y-%m-%d') - _td(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
            _end_utc = (_dt.strptime(today, '%Y-%m-%d') + _td(days=1) - _td(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
            today_count = conn.execute(
                "SELECT COUNT(*) as total FROM numer_memory "
                "WHERE user_id = ? "
                "AND created_at >= ? AND created_at < ?",
                (identifier, _start_utc, _end_utc)
            ).fetchone()['total']
        
        # Частые темы
        tags_row = conn.execute(
            "SELECT metadata FROM numer_memory WHERE user_id = ? AND metadata != '{}' ORDER BY created_at DESC LIMIT 100",
            (identifier,)
        ).fetchall()
        
        tag_counts = {}
        for row in tags_row:
            try:
                meta = json.loads(row['metadata'])
                section = meta.get('section', '')
                if section:
                    tag_counts[section] = tag_counts.get(section, 0) + 1
            except:
                pass
        
        frequent_topics = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Записи с пагинацией
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        rows = conn.execute(query, params).fetchall()
    
    memories = []
    for r in rows:
        meta = {}
        try:
            meta = json.loads(r['metadata'])
        except:
            pass
        
        memories.append({
            'type': r['type'],
            'content': r['content'][:300],
            'section': meta.get('section', ''),
            'time_of_day': meta.get('time_of_day', ''),
            'created_at': r['created_at']
        })
    
    return jsonify({
        'memories': memories,
        'total': total_count,
        'today': today_count,
        'frequent_topics': [{'name': t[0], 'count': t[1]} for t in frequent_topics],
        'has_more': (offset + limit) < total_count
    })

@app.route('/api/numer/dialogue/stream', methods=['POST'])
@csrf_required
@limiter.limit("15 per minute;150 per hour")
def api_numer_dialogue_stream():
    data = request.json or {}
    message = data.get('message', '').strip()
    section = data.get('section', 'general')
    # context читается так же, как в api_numer_dialogue — он нужен build_system_prompt
    # для правил financial_code / horoscope / compatibility (цифры кода, знак зодиака и т. д.).
    context = data.get('context', {})
    
    if not message:
        return jsonify({"error": "Пустое сообщение"}), 400
    
    limit_check = _check_daily_question_limit()
    if limit_check:
        return limit_check
    
    identifier = get_identifier()
    portrait = get_or_create_portrait(identifier)
    live_context = None
    try:
        from utils.orchestrator import get_live_context
        live_context = get_live_context(identifier)
    except:
        pass
    memories = []
    try:
        from utils.orchestrator import get_recent_memories
        memories = get_recent_memories(identifier, limit=5)
    except:
        pass

    system_prompt = ""
    try:
        from utils.orchestrator import build_system_prompt
        system_prompt = build_system_prompt(portrait, live_context or {}, memories, section, context)
    except:
        system_prompt = "Ты — unanum, проводница."

    # Импорты, нужные и для чтения кэша (до генератора), и для стрима (внутри).
    from utils.ai_service import (
        ask_deepseek_stream,
        _get_cache_key,
        _get_from_cache,
        _save_to_cache,
        compute_portrait_hash,
    )
    from utils.stream_helpers import format_sse

    # Кэш: ключ считаем один раз ДО генератора (внутри генератора уже нельзя — flask.g недоступен).
    # portrait_hash считаем снаружи — чтобы _get_cache_key не делал лишний SELECT к user_portrait.
    portrait_hash = compute_portrait_hash(portrait)
    cache_key = _get_cache_key(system_prompt, message, identifier, portrait_hash)
    cached = _get_from_cache(cache_key)

    def generate():
        # event: meta — первый, сразу после старта потока (по контракту).
        yield format_sse('meta', {'section': section})

        if cached:
            # Кэш-хит: отдаём весь текст одним chunk + done.
            # Стримить нечего — DeepSeek не вызываем, токены не тратим.
            yield format_sse('chunk', {'chunk': cached})
            yield format_sse('done', {'full_text': cached, 'cached': True})
        else:
            full_text = ""
            try:
                for chunk in ask_deepseek_stream(system_prompt, message, temperature=0.85):
                    if chunk is None:
                        break
                    full_text += chunk
                    yield format_sse('chunk', {'chunk': chunk})

                # Сохраняем в кэш только непустой ответ — иначе забьём кэш огрызками
                # при обрыве соединения или ошибке DeepSeek.
                if full_text:
                    _save_to_cache(cache_key, full_text)

                yield format_sse('done', {'full_text': full_text})
            except Exception:
                yield format_sse('error', {
                    'message': 'Прости, что-то пошло не так. Попробуй ещё раз.'
                })

        # save_memory — всегда: и при кэш-хите, и после живого стрима.
        # Дневной лимит вопросов считается по numer_memory (type='dialogue'),
        # поэтому запись обязательна — иначе лимит не инкрементируется.
        try:
            from utils.orchestrator import save_memory
            save_memory(identifier, "dialogue", message[:100], {"section": section})
        except Exception:
            pass

    # Заголовки против буферизации:
    #   Cache-Control — браузер и прокси не кэшируют SSE-поток.
    #   X-Accel-Buffering: no — Nginx не буферизует ответ от upstream.
    #     Это критично для прода: без него Nginx копит весь ответ и отдаёт одним куском.
    headers = {
        'Cache-Control': 'no-cache, no-transform',
        'X-Accel-Buffering': 'no',
    }
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers=headers,
    )

# ========== Share Card Generator ==========
def generate_card_png(data):
    """Чистый рендер PNG-карточки (без Flask) — выполняется в ProcessPool."""
    from utils.share_card import load_font
    from PIL import Image, ImageDraw, ImageFont
    import io
    import textwrap

    card_type = data.get('type', 'financial-code')
    title = data.get('title', 'unanum')
    subtitle = data.get('subtitle', '')
    main_text = data.get('main_text', '')
    footer = data.get('footer', 'unanum')
    tariff = data.get('tariff', 'Искра')

    width, height = 1080, 1920
    margin = 50

    bg_colors = {
        'Искра': '#1a1a2e',
        'Пламя': '#0d0d1a'
    }
    img = Image.new('RGB', (width, height), bg_colors.get(tariff, '#1a1a2e'))
    draw = ImageDraw.Draw(img)

    if tariff == 'Пламя':
        try:
            frame_path = os.path.join('static', 'images', 'share-frame-premium.png')
            if os.path.exists(frame_path):
                frame = Image.open(frame_path).resize((1080, 1920)).convert('RGBA')
                img.paste(frame, (0, 0), frame)
        except Exception:
            pass

    if tariff != 'Пламя':
        frame_colors = {
            'Искра': (212, 135, 154),
            'Пламя': (212, 168, 67),
        }
        frame_widths = {
            'Искра': 2,
            'Пламя': 3,
        }
        frame_color = frame_colors.get(tariff, (212, 168, 67))
        frame_width = frame_widths.get(tariff, 2)
        draw.rectangle(
            [(margin, margin), (width - margin, height - margin)],
            outline=frame_color,
            width=frame_width
        )

    font_title = load_font(40)
    font_main = load_font(90)
    font_text = load_font(32)
    font_footer = load_font(28)

    title_color = (212, 168, 67) if tariff != 'Искра' else (232, 168, 181)
    main_color = (212, 168, 67) if tariff != 'Искра' else (255, 255, 255)

    y = margin + 60

    if title:
        draw.text((margin + 20, y), title, fill=title_color, font=font_title)
        y += 80

    if subtitle:
        bbox = draw.textbbox((0, 0), subtitle, font=font_main)
        sw = bbox[2] - bbox[0]
        draw.text(((width - sw) / 2, y), subtitle, fill=main_color, font=font_main)
        y += bbox[3] - bbox[1] + 40

    if main_text:
        if len(main_text) > 200:
            main_text = main_text[:200] + '...'
        content_width = width - margin * 2 - 80
        test_char_w = draw.textbbox((0, 0), "a", font=font_text)[2]
        chars_per_line = max(1, content_width // test_char_w)

        lines = main_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                y += 16
                continue
            wrapped = textwrap.fill(line, width=chars_per_line)
            for tl in wrapped.split('\n'):
                bbox = draw.textbbox((0, 0), tl, font=font_text)
                tw = bbox[2] - bbox[0]
                draw.text(((width - tw) / 2, y), tl, fill=(255, 255, 255), font=font_text)
                y += bbox[3] - bbox[1] + 8

    footer_bbox = draw.textbbox((0, 0), footer, font=font_footer)
    fw = footer_bbox[2] - footer_bbox[0]
    draw.text(((width - fw) / 2, height - 100), footer, fill=(160, 139, 150), font=font_footer)

    if tariff == 'Искра':
        watermark_font = load_font(24)
        draw.text((width - 280, height - 140), 'unanum', fill=(255, 255, 255), font=watermark_font)

    img_io = io.BytesIO()
    img.save(img_io, 'PNG', quality=95)
    img_io.seek(0)

    return (img_io.getvalue(), 'image/png', f'{card_type}-card.png')

@app.route('/api/generate-card', methods=['POST'])
@limiter.limit("5 per minute")
@csrf_required
def api_generate_card():
    data = request.json or {}
    body, mimetype, filename = run_image_job(generate_card_png, data)
    return Response(
        body,
        mimetype=mimetype,
        headers={'Content-Disposition': f'attachment;filename={filename}'}
    )


# ========== Share Citations ==========
@app.route('/api/share/citations', methods=['POST'])
@csrf_required
def api_share_citations():
    data = request.json or {}
    full_text = data.get('text', '')
    portal = data.get('portal', '')

    if not full_text:
        return jsonify({"citations": []})

    from utils.ai_service import ai_share_citations
    citations = ai_share_citations(full_text, portal)
    return jsonify({"citations": citations})

# ========== Admin Panel ==========
@app.route('/admin')
def admin_login_page():
    if session.get('admin_authenticated'):
        return redirect('/admin/panel')
    return render_template('admin_login.html')

@app.route('/admin/panel')
def admin_panel():
    if not session.get('admin_authenticated'):
        return redirect('/admin')
    return render_template('admin_panel.html')

@app.route('/api/admin/login', methods=['POST'])
@csrf_required
@limiter.limit("5 per minute;20 per hour")
def api_admin_login():
    ADMIN_PASSWORD = Config.ADMIN_MASTER_PASSWORD
    data = request.json or {}
    # hmac.compare_digest работает только со str/bytes.
    # Если клиент пришлёт {"password": null} или число — приведём к str,
    # чтобы не получить TypeError → 500.
    raw_password = data.get('password', '')
    password = str(raw_password) if raw_password is not None else ''

    if not ADMIN_PASSWORD:
        return jsonify({"error": "Admin password not configured"}), 500

    # hmac.compare_digest — constant-time сравнение (защита от timing attack)
    if hmac.compare_digest(password, ADMIN_PASSWORD):
        session['admin_authenticated'] = True
        session['admin_ip'] = request.remote_addr
        session.permanent = True
        return jsonify({"success": True, "redirect": "/admin/panel"})

    return jsonify({"error": "Неверный пароль"}), 403

@app.route('/api/admin/logout', methods=['POST'])
@csrf_required
def api_admin_logout():
    session.pop('admin_authenticated', None)
    return jsonify({"success": True})

@app.route('/api/admin/prompts', methods=['GET'])
@admin_required
def api_get_prompts():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM prompts ORDER BY name").fetchall()
        prompts = [{"name": r['name'], "content": r['content']} for r in rows]
    return jsonify(prompts)

@app.route('/api/admin/prompts', methods=['POST'])
@admin_required
@csrf_required
def api_update_prompt():
    data = request.json or {}
    name = data.get('name')
    content = data.get('content')
    with get_db() as conn:
        conn.execute(
            "UPDATE prompts SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE name = ?",
            (content, name)
        )
        conn.commit()
    clear_ai_cache()
    add_log('INFO', 'admin', f"Промпт '{name}' обновлён, кэш очищен")
    return jsonify({"success": True})

@app.route('/api/admin/logs', methods=['GET'])
@admin_required
def api_get_logs():
    limit = request.args.get('limit', 50, type=int)
    limit = max(1, min(limit, 500))
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM logs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        logs = [dict(r) for r in rows]
    return jsonify(logs)

@app.route('/api/admin/cache/clear', methods=['POST'])
@admin_required
@csrf_required
def api_clear_cache():
    clear_ai_cache()
    add_log('INFO', 'admin', 'Кэш ИИ очищен вручную')
    return jsonify({"success": True})

@app.route('/api/admin/user/subscription', methods=['POST'])
@admin_required
@csrf_required
def api_admin_set_subscription():
    data = request.json or {}
    # data.get('email', '') вернёт None, если ключ есть, но значение = null
    # (например, {"email": null}). None.strip() → AttributeError → 500.
    # Поэтому сначала .get('email') (без дефолта), потом `or ''`.
    email = (data.get('email') or '').strip()
    tariff = (data.get('tariff') or '').strip()

    if not email or tariff not in ['Искра', 'Пламя']:
        return jsonify({"error": "Неверные данные"}), 400

    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            return jsonify({"error": "Пользователь не найден"}), 404

        conn.execute("UPDATE users SET subscription = ? WHERE email = ?", (tariff, email))
        conn.commit()

    add_log('INFO', 'admin', f"Тариф пользователя {email} изменён на {tariff}")
    return jsonify({"success": True, "message": f"Тариф для {email} установлен: {tariff}"})

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def api_admin_get_users():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT email, name, subscription, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
        users = [dict(r) for r in rows]
    return jsonify(users)

# ========== Share System Admin API ==========
@app.route('/api/admin/share/backgrounds', methods=['GET'])
@admin_required
def api_get_share_backgrounds():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM share_backgrounds ORDER BY created_at DESC").fetchall()
        return jsonify([dict(r) for r in rows])

@app.route('/api/admin/share/backgrounds', methods=['POST'])
@admin_required
@csrf_required
def api_add_share_background():
    if 'image' not in request.files:
        return jsonify({"error": "Файл не загружен"}), 400
    
    file = request.files['image']
    name = request.form.get('name', 'Без названия')
    tariff = request.form.get('tariff', 'Искра')
    
    if file.content_type not in ALLOWED_IMAGE_MIME:
        return jsonify({"error": "Разрешены только PNG, JPEG, WebP, GIF"}), 400
    
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_IMAGE_SIZE:
        return jsonify({"error": "Размер файла не более 5 МБ"}), 400
    
    ext_map = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp', 'image/gif': 'gif'}
    ext = ext_map.get(file.content_type, 'png')
    filename = f"bg_{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join('static', 'images', 'share', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file.save(filepath)

    # Валидация содержимого: проверяем, что файл действительно является изображением
    try:
        from PIL import Image
        with Image.open(filepath) as im:
            im.verify()
    except Exception:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({"error": "Файл не является корректным изображением"}), 400

    with get_db() as conn:
        conn.execute(
            "INSERT INTO share_backgrounds (name, image_path, tariff) VALUES (?, ?, ?)",
            (name, f'/static/images/share/{filename}', tariff)
        )
    
    return jsonify({"success": True})

@app.route('/api/admin/share/backgrounds/<int:bg_id>', methods=['DELETE'])
@admin_required
@csrf_required
def api_delete_share_background(bg_id):
    with get_db() as conn:
        row = conn.execute("SELECT image_path FROM share_backgrounds WHERE id = ?", (bg_id,)).fetchone()
        if row and os.path.exists(row['image_path'].lstrip('/')):
            os.remove(row['image_path'].lstrip('/'))
        conn.execute("DELETE FROM share_backgrounds WHERE id = ?", (bg_id,))
    return jsonify({"success": True})


# ========== Share Card Generator (с поддержкой GIF для Пламени) ==========
def generate_share_card(data):
    """Чистый рендер share-карточки (PNG/GIF) — выполняется в ProcessPool."""
    from utils.share_card import load_font, render_text_layer, apply_text_shape
    from PIL import Image, ImageDraw, ImageFont
    import io
    import textwrap

    text = data.get('text', '')
    template_id = data.get('template_id', None)
    tariff = data.get('tariff', 'Искра')

    width, height = 1080, 1920
    margin = 80

    bg_color = (10, 26, 10)
    bg_image = None
    text_color = (255, 213, 79)
    align = 'center'
    shadow_color = (0, 0, 0)
    shadow_offset = (2, 2)
    shadow_blur = 4
    watermark_img = None
    wm_pos_x = 40
    wm_pos_y = 1660
    font_size_min = 32
    font_size_max = 60
    text_shape = 'rectangle'
    template_elements = []

    with get_db() as conn:
        # Один JOIN вместо 4 отдельных запросов
        template_sql_base = """
            SELECT
                t.*,
                b.image_path   AS bg_image_path,
                b.is_active    AS bg_is_active,
                s.color        AS st_color,
                s.align        AS st_align,
                s.shadow_color AS st_shadow_color,
                s.shadow_offset AS st_shadow_offset,
                s.shadow_blur  AS st_shadow_blur,
                s.font_size_min AS st_font_size_min,
                s.font_size_max AS st_font_size_max,
                s.text_shape   AS st_text_shape,
                s.is_active    AS st_is_active,
                w.image_path   AS wm_image_path,
                w.pos_x        AS wm_pos_x,
                w.pos_y        AS wm_pos_y,
                w.size_percent AS wm_size_percent,
                w.is_active    AS wm_is_active
            FROM share_templates t
            LEFT JOIN share_backgrounds  b ON t.background_id  = b.id
            LEFT JOIN share_text_styles  s ON t.text_style_id  = s.id
            LEFT JOIN share_watermarks   w ON t.watermark_id   = w.id
        """

        if template_id:
            template = conn.execute(
                template_sql_base + " WHERE t.id = ? AND t.is_active = 1",
                (template_id,)
            ).fetchone()
        else:
            template = conn.execute(
                template_sql_base + " WHERE t.is_default = 1 AND t.tariff = ? AND t.is_active = 1 LIMIT 1",
                (tariff,)
            ).fetchone()
            if not template:
                template = conn.execute(
                    template_sql_base + " WHERE t.is_default = 1 AND t.is_active = 1 LIMIT 1"
                ).fetchone()

        if template:
            # Загружаем элементы шаблона (координаты)
            template_elements = conn.execute(
                "SELECT * FROM share_template_elements WHERE template_id = ?",
                (template['id'],)
            ).fetchall()
            template_elements = [dict(r) for r in template_elements]

            # Background
            if template.get('bg_image_path') and os.path.exists(template['bg_image_path'].lstrip('/')):
                bg_img = Image.open(template['bg_image_path'].lstrip('/'))
                bg_img.thumbnail((width, height), Image.LANCZOS)
                bg_image = bg_img.convert('RGBA')

            # Text style
            if template.get('st_color'):
                text_color = tuple(int(template['st_color'].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
                align = template['st_align']
                shadow_color = tuple(int(template['st_shadow_color'].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
                shadow_offset = tuple(map(int, template['st_shadow_offset'].split(',')))
                shadow_blur = template['st_shadow_blur']
                font_size_min = template['st_font_size_min']
                font_size_max = template['st_font_size_max']
                text_shape = template['st_text_shape'] if template['st_text_shape'] else 'rectangle'

            # Watermark
            if template.get('wm_image_path') and os.path.exists(template['wm_image_path'].lstrip('/')):
                watermark_img = Image.open(template['wm_image_path'].lstrip('/')).convert('RGBA')
                wm_pos_x = template['wm_pos_x'] if template['wm_pos_x'] is not None else 40
                wm_pos_y = template['wm_pos_y'] if template['wm_pos_y'] is not None else 1660
                wm_size_percent = template['wm_size_percent'] if template['wm_size_percent'] is not None else 20
                wm_w = int(width * wm_size_percent / 100)
                wm_h = int(wm_w * watermark_img.size[1] / watermark_img.size[0])
                watermark_img = watermark_img.resize((wm_w, wm_h))

    # --- Создаём временное изображение и draw для подбора шрифта ---
    temp_img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(temp_img)

    # Подбор размера шрифта (только если нет элементов шаблона с текстом)
    font = load_font(font_size_max)
    lines = []
    if not template_elements:
        font_size = font_size_max
        while font_size >= font_size_min:
            font = load_font(font_size)
            lines = []
            for paragraph in text.split('\n'):
                if paragraph.strip():
                    lines.extend(textwrap.wrap(paragraph.strip(), width=40))
                else:
                    lines.append('')
            total_height = sum(
                draw.textbbox((0, 0), line, font=font)[3] - draw.textbbox((0, 0), line, font=font)[1] + 12
                for line in lines
            ) if lines else 0
            if total_height <= height - margin * 2 - 200:
                break
            font_size -= 2

    # --- Отрисовка в зависимости от тарифа ---
    if tariff == 'Пламя':
        frames = []
        for frame_idx in range(12):
            if bg_image:
                frame = bg_image.copy()
            else:
                frame = Image.new('RGB', (width, height), bg_color)
            draw = ImageDraw.Draw(frame)
            
            shift = int(frame_idx * 255 / 12)
            r = (text_color[0] + shift) % 256
            g = (text_color[1] + shift // 2) % 256
            b = (text_color[2] + shift // 3) % 256
            frame_text_color = (r, g, b)
            
            if template_elements:
                for el in template_elements:
                    if el['type'] == 'text':
                        display_text = el['text']
                        if el.get('placeholder') and text:
                            display_text = text
                        
                        # Вычисляем bounding box (масштаб 3x)
                        scale = 3
                        el_x1 = el.get('x1', 100) * scale
                        el_y1 = el.get('y1', 300) * scale
                        el_x2 = el.get('x2', 260) * scale
                        el_y2 = el.get('y2', 300) * scale
                        el_x3 = el.get('x3', 260) * scale
                        el_y3 = el.get('y3', 360) * scale
                        el_x4 = el.get('x4', 100) * scale
                        el_y4 = el.get('y4', 360) * scale
                        
                        min_x = min(el_x1, el_x2, el_x3, el_x4)
                        min_y = min(el_y1, el_y2, el_y3, el_y4)
                        max_x = max(el_x1, el_x2, el_x3, el_x4)
                        max_y = max(el_y1, el_y2, el_y3, el_y4)
                        
                        box_w = max_x - min_x
                        box_h = max_y - min_y
                        
                        el_color = tuple(int(el['color'].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
                        
                        # Подбираем шрифт, чтобы текст полностью заполнил блок
                        font_size = 200
                        frame_draw = ImageDraw.Draw(frame)
                        test_font = None
                        wrapped_lines = []
                        line_height = 0
                        total_h = 0
                        
                        while font_size >= 8:
                            test_font = load_font(font_size)
                            
                            # Переносим текст с учётом ширины блока
                            char_width = frame_draw.textbbox((0, 0), "A", font=test_font)[2]
                            chars_per_line = max(1, int(box_w / char_width))
                            wrapped_text = textwrap.fill(display_text, width=chars_per_line)
                            wrapped_lines = wrapped_text.split('\n')
                            
                            # Считаем высоту всех строк
                            line_height = frame_draw.textbbox((0, 0), "Ag", font=test_font)[3] + 2
                            total_h = len(wrapped_lines) * line_height
                            
                            if total_h <= box_h:
                                break
                            
                            font_size -= 2
                        
                        # Если не влезло даже минимальным шрифтом — обрезаем строки
                        if font_size < 8:
                            font_size = 8
                            test_font = load_font(font_size)
                            char_width = frame_draw.textbbox((0, 0), "A", font=test_font)[2]
                            chars_per_line = max(1, int(box_w / char_width))
                            wrapped_text = textwrap.fill(display_text, width=chars_per_line)
                            wrapped_lines = wrapped_text.split('\n')
                            line_height = frame_draw.textbbox((0, 0), "Ag", font=test_font)[3] + 2
                            max_lines = int(box_h // line_height)
                            wrapped_lines = wrapped_lines[:max_lines]
                            if wrapped_lines:
                                wrapped_lines[-1] = wrapped_lines[-1] + '…'
                            total_h = len(wrapped_lines) * line_height
                        
                        # Рисуем с гарантированной обрезкой по ширине
                        center_y = min_y + (box_h - total_h) // 2
                        for line in wrapped_lines:
                            # Обрезаем строку, если она шире блока
                            lw = frame_draw.textbbox((0, 0), line, font=test_font)[2]
                            while lw > box_w and len(line) > 1:
                                line = line[:-1]
                                lw = frame_draw.textbbox((0, 0), line + '…', font=test_font)[2]
                                if lw <= box_w:
                                    line = line + '…'
                                    lw = frame_draw.textbbox((0, 0), line, font=test_font)[2]
                                    break
                            
                            lx = min_x
                            # Убедимся, что текст не выходит за левую границу
                            if lx < min_x:
                                lx = min_x
                            # Убедимся, что текст не выходит за правую границу
                            if lx + lw > max_x:
                                lx = max_x - lw
                            
                            if shadow_blur > 0:
                                frame_draw.text((lx + shadow_offset[0], center_y + shadow_offset[1]), line, fill=shadow_color, font=test_font)
                            frame_draw.text((lx, center_y), line, fill=el_color, font=test_font)
                            center_y += line_height
                    elif el['type'] == 'watermark' and watermark_img:
                        el_x = min(el.get('x1', 0), el.get('x2', 0), el.get('x3', 0), el.get('x4', 0))
                        el_y = min(el.get('y1', 0), el.get('y2', 0), el.get('y3', 0), el.get('y4', 0))
                        frame.paste(watermark_img, (el_x, el_y), watermark_img)
            else:
                y = margin + 100
                for line in lines:
                    if not line:
                        y += 16
                        continue
                    bbox = draw.textbbox((0, 0), line, font=font)
                    tw = bbox[2] - bbox[0]
                    if align == 'center':
                        x = (width - tw) / 2
                    elif align == 'right':
                        x = width - margin - tw
                    else:
                        x = margin
                    
                    if shadow_blur > 0:
                        draw.text((x + shadow_offset[0], y + shadow_offset[1]), line, fill=shadow_color, font=font)
                    draw.text((x, y), line, fill=frame_text_color, font=font)
                    y += bbox[3] - bbox[1] + 12
                    
                if watermark_img:
                    frame.paste(watermark_img, (wm_pos_x, wm_pos_y), watermark_img)
            
            frames.append(frame)
        
        gif_io = io.BytesIO()
        frames[0].save(
            gif_io,
            format='GIF',
            save_all=True,
            append_images=frames[1:],
            duration=200,
            loop=0,
            optimize=True
        )
        gif_io.seek(0)
        
        return (gif_io.getvalue(), 'image/gif', 'numer-share-card.gif')

    # Статичный PNG (Путница, Провидец)
    if bg_image:
        img = bg_image
    else:
        img = Image.new('RGB', (width, height), bg_color)

    if template_elements:
        # Рисуем элементы по координатам из шаблона
        for el in template_elements:
            if el['type'] == 'text':
                display_text = el['text']
                if el.get('placeholder') and text:
                    display_text = text
                
                # Вычисляем bounding box (масштаб 3x)
                scale = 3
                el_x1 = el.get('x1', 100) * scale
                el_y1 = el.get('y1', 300) * scale
                el_x2 = el.get('x2', 260) * scale
                el_y2 = el.get('y2', 300) * scale
                el_x3 = el.get('x3', 260) * scale
                el_y3 = el.get('y3', 360) * scale
                el_x4 = el.get('x4', 100) * scale
                el_y4 = el.get('y4', 360) * scale
                
                min_x = min(el_x1, el_x2, el_x3, el_x4)
                min_y = min(el_y1, el_y2, el_y3, el_y4)
                max_x = max(el_x1, el_x2, el_x3, el_x4)
                max_y = max(el_y1, el_y2, el_y3, el_y4)
                
                box_w = max_x - min_x
                box_h = max_y - min_y
                
                el_color = tuple(int(el['color'].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
                
                # Подбираем шрифт, чтобы текст полностью заполнил блок
                font_size = 200
                img_draw = ImageDraw.Draw(img)
                test_font = None
                wrapped_lines = []
                line_height = 0
                total_h = 0
                
                while font_size >= 8:
                    test_font = load_font(font_size)
                    
                    # Переносим текст с учётом ширины блока
                    char_width = img_draw.textbbox((0, 0), "A", font=test_font)[2]
                    chars_per_line = max(1, int(box_w / char_width))
                    wrapped_text = textwrap.fill(display_text, width=chars_per_line)
                    wrapped_lines = wrapped_text.split('\n')
                    
                    # Считаем высоту всех строк
                    line_height = img_draw.textbbox((0, 0), "Ag", font=test_font)[3] + 2
                    total_h = len(wrapped_lines) * line_height
                    
                    if total_h <= box_h:
                        break
                    
                    font_size -= 2
                
                # Если не влезло даже минимальным шрифтом — обрезаем строки
                if font_size < 8:
                    font_size = 8
                    test_font = load_font(font_size)
                    char_width = img_draw.textbbox((0, 0), "A", font=test_font)[2]
                    chars_per_line = max(1, int(box_w / char_width))
                    wrapped_text = textwrap.fill(display_text, width=chars_per_line)
                    wrapped_lines = wrapped_text.split('\n')
                    line_height = img_draw.textbbox((0, 0), "Ag", font=test_font)[3] + 2
                    max_lines = int(box_h // line_height)
                    wrapped_lines = wrapped_lines[:max_lines]
                    if wrapped_lines:
                        wrapped_lines[-1] = wrapped_lines[-1] + '…'
                    total_h = len(wrapped_lines) * line_height
                
                # Рисуем с гарантированной обрезкой по ширине
                center_y = min_y + (box_h - total_h) // 2
                for line in wrapped_lines:
                    # Обрезаем строку, если она шире блока
                    lw = img_draw.textbbox((0, 0), line, font=test_font)[2]
                    while lw > box_w and len(line) > 1:
                        line = line[:-1]
                        lw = img_draw.textbbox((0, 0), line + '…', font=test_font)[2]
                        if lw <= box_w:
                            line = line + '…'
                            lw = img_draw.textbbox((0, 0), line, font=test_font)[2]
                            break
                    
                    lx = min_x
                    # Убедимся, что текст не выходит за левую границу
                    if lx < min_x:
                        lx = min_x
                    # Убедимся, что текст не выходит за правую границу
                    if lx + lw > max_x:
                        lx = max_x - lw
                    
                    if shadow_blur > 0:
                        img_draw.text((lx + shadow_offset[0], center_y + shadow_offset[1]), line, fill=shadow_color, font=test_font)
                    img_draw.text((lx, center_y), line, fill=el_color, font=test_font)
                    center_y += line_height
            elif el['type'] == 'watermark' and watermark_img:
                el_x = min(el.get('x1', 0), el.get('x2', 0), el.get('x3', 0), el.get('x4', 0))
                el_y = min(el.get('y1', 0), el.get('y2', 0), el.get('y3', 0), el.get('y4', 0))
                img.paste(watermark_img, (el_x, el_y), watermark_img)
    else:
        text_layer = render_text_layer(lines, font, text_color, shadow_color, shadow_offset, align, width, height, margin)
        text_layer = apply_text_shape(text_layer, text_shape, width, height)
        img.paste(text_layer, (0, 0), text_layer)
        
        if watermark_img:
            img.paste(watermark_img, (wm_pos_x, wm_pos_y), watermark_img)

    img_io = io.BytesIO()
    img.save(img_io, 'PNG', quality=95)
    img_io.seek(0)

    return (img_io.getvalue(), 'image/png', 'numer-share-card.png')

@app.route('/api/generate-share-card', methods=['POST'])
@limiter.limit("5 per minute")
@csrf_required
def api_generate_share_card():
    data = request.json or {}
    text = data.get('text', '')
    if not text:
        return jsonify({"error": "Текст не передан"}), 400
    if len(text) > 3000:
        return jsonify({"error": "Текст слишком длинный (макс. 3000 символов)"}), 400

    body, mimetype, filename = run_image_job(generate_share_card, data)
    return Response(
        body,
        mimetype=mimetype,
        headers={'Content-Disposition': f'attachment;filename={filename}'}
    )


# ========== Share Text Styles API ==========
@app.route('/api/admin/share/text-styles', methods=['GET'])
@admin_required
def api_get_share_text_styles():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM share_text_styles ORDER BY created_at DESC").fetchall()
        return jsonify([dict(r) for r in rows])

@app.route('/api/admin/share/text-styles', methods=['POST'])
@admin_required
@csrf_required
def api_add_share_text_style():
    data = request.json or {}
    name = data.get('name', 'Новый стиль')
    color = data.get('color', '#ffd54f')
    align = data.get('align', 'center')
    text_shape = data.get('text_shape', 'rectangle')
    font_size_min = data.get('font_size_min', 32)
    font_size_max = data.get('font_size_max', 60)
    tariff = data.get('tariff', 'Искра')

    with get_db() as conn:
        conn.execute(
            """INSERT INTO share_text_styles (name, color, align, text_shape, font_size_min, font_size_max, tariff)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, color, align, text_shape, font_size_min, font_size_max, tariff)
        )
    return jsonify({"success": True})

@app.route('/api/admin/share/text-styles/<int:style_id>', methods=['DELETE'])
@admin_required
@csrf_required
def api_delete_share_text_style(style_id):
    with get_db() as conn:
        conn.execute("DELETE FROM share_text_styles WHERE id = ?", (style_id,))
    return jsonify({"success": True})


@app.route('/api/admin/share/text-styles/<int:style_id>', methods=['PUT'])
@admin_required
@csrf_required
def api_update_share_text_style(style_id):
    data = request.json or {}
    text_shape = data.get('text_shape')
    
    if text_shape:
        with get_db() as conn:
            conn.execute("UPDATE share_text_styles SET text_shape = ? WHERE id = ?", (text_shape, style_id))
    
    return jsonify({"success": True})

# ========== Share Watermarks API ==========
@app.route('/api/admin/share/watermarks', methods=['GET'])
@admin_required
def api_get_share_watermarks():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM share_watermarks ORDER BY created_at DESC").fetchall()
        return jsonify([dict(r) for r in rows])

@app.route('/api/admin/share/watermarks', methods=['POST'])
@admin_required
@csrf_required
def api_add_share_watermark():
    if 'image' not in request.files:
        return jsonify({"error": "Файл не загружен"}), 400

    file = request.files['image']
    name = request.form.get('name', 'Без названия')
    position = request.form.get('position', 'bottom-right')
    pos_x = request.form.get('pos_x', 40, type=int)
    pos_y = request.form.get('pos_y', 1660, type=int)
    size_percent = request.form.get('size_percent', 20, type=int)
    tariff = request.form.get('tariff', 'Искра')

    if file.content_type not in ALLOWED_IMAGE_MIME:
        return jsonify({"error": "Разрешены только PNG, JPEG, WebP, GIF"}), 400

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_IMAGE_SIZE:
        return jsonify({"error": "Размер файла не более 5 МБ"}), 400

    ext_map = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp', 'image/gif': 'gif'}
    ext = ext_map.get(file.content_type, 'png')
    filename = f"wm_{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join('static', 'images', 'share', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file.save(filepath)

    # Валидация содержимого: проверяем, что файл действительно является изображением
    try:
        from PIL import Image
        with Image.open(filepath) as im:
            im.verify()
    except Exception:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({"error": "Файл не является корректным изображением"}), 400

    with get_db() as conn:
        conn.execute(
            "INSERT INTO share_watermarks (name, image_path, position, pos_x, pos_y, size_percent, tariff) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, f'/static/images/share/{filename}', position, pos_x, pos_y, size_percent, tariff)
        )
    return jsonify({"success": True})

@app.route('/api/admin/share/watermarks/<int:wm_id>', methods=['DELETE'])
@admin_required
@csrf_required
def api_delete_share_watermark(wm_id):
    with get_db() as conn:
        row = conn.execute("SELECT image_path FROM share_watermarks WHERE id = ?", (wm_id,)).fetchone()
        if row and row['image_path'] and os.path.exists(row['image_path'].lstrip('/')):
            os.remove(row['image_path'].lstrip('/'))
        conn.execute("DELETE FROM share_watermarks WHERE id = ?", (wm_id,))
    return jsonify({"success": True})

@app.route('/api/admin/share/templates/save-full', methods=['POST'])
@admin_required
@csrf_required
def api_save_full_template():
    data = request.json or {}
    name = data.get('name', 'Новый шаблон')
    background_path = data.get('background', '')
    elements = data.get('elements', [])
    tariff = data.get('tariff', 'Искра')
    is_default = data.get('is_default', 0)
    
    # Ищем или создаём background_id
    background_id = None
    if background_path:
        with get_db() as conn:
            bg = conn.execute("SELECT id FROM share_backgrounds WHERE image_path = ?", (background_path,)).fetchone()
            if bg:
                background_id = bg['id']
    
    # Создаём текстовый стиль из первого текстового элемента
    text_style_id = None
    text_shape = 'rectangle'
    text_color = '#ffd54f'
    font_size = 24
    
    for el in elements:
        if el.get('type') == 'text':
            text_shape = el.get('shape', 'rectangle')
            text_color = el.get('color', '#ffd54f')
            font_size = el.get('fontSize', 24)
            break
    
    with get_db() as conn:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute(
                "INSERT INTO share_text_styles (name, color, align, text_shape, font_size_min, font_size_max, tariff) VALUES (%s, %s, 'center', %s, %s, %s, %s) RETURNING id",
                (f'{name} (стиль)', text_color, text_shape, font_size, font_size, tariff)
            )
            row = cur.fetchone()
            text_style_id = row['id']
        else:
            cur.execute(
                "INSERT INTO share_text_styles (name, color, align, text_shape, font_size_min, font_size_max, tariff) VALUES (?, ?, 'center', ?, ?, ?, ?)",
                (f'{name} (стиль)', text_color, text_shape, font_size, font_size, tariff)
            )
            text_style_id = cur.lastrowid
    
    # Создаём запись водяного знака (если есть).
    # В шаблоне используем первый watermark-элемент; имя берём из seed_share_defaults → 'Numer'.
    # Если элемента нет — попробуем найти любой активный дефолтный.
    watermark_id = None
    has_watermark_element = any(el.get('type') == 'watermark' for el in elements)
    if has_watermark_element:
        with get_db() as wm_conn:
            wm = wm_conn.execute(
                "SELECT id FROM share_watermarks WHERE is_active = 1 ORDER BY id LIMIT 1"
            ).fetchone()
            if wm:
                watermark_id = wm['id']
    
    # Сохраняем шаблон
    with get_db() as conn:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute(
                "INSERT INTO share_templates (name, background_id, text_style_id, watermark_id, is_default, tariff) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (name, background_id, text_style_id, watermark_id, is_default, tariff)
            )
            row = cur.fetchone()
            template_id = row['id']
        else:
            cur.execute(
                "INSERT INTO share_templates (name, background_id, text_style_id, watermark_id, is_default, tariff) VALUES (?, ?, ?, ?, ?, ?)",
                (name, background_id, text_style_id, watermark_id, is_default, tariff)
            )
            template_id = cur.lastrowid
        
        # Таблица share_template_elements гарантированно создана в init_db()
        # (с колонками image_path и placeholder). Повторный CREATE не нужен.
        c = conn.cursor()
        
        for el in elements:
            c.execute(
                """INSERT INTO share_template_elements (template_id, type, text, color, shape, font_size, placeholder, image_path, x1, y1, x2, y2, x3, y3, x4, y4)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (template_id, el.get('type', 'text'), el.get('text', ''), el.get('color', '#ffd54f'),
                el.get('shape', 'free'), el.get('fontSize', 24), el.get('placeholder', 0),
                el.get('imagePath', ''),
                el.get('x1', 100), el.get('y1', 300),
                el.get('x2', 260), el.get('y2', 300),
                el.get('x3', 260), el.get('y3', 360),
                el.get('x4', 100), el.get('y4', 360))
            )
    
    return jsonify({"success": True, "template_id": template_id})

@app.route('/api/admin/share/template-elements/<int:template_id>', methods=['GET'])
@admin_required
def api_get_template_elements(template_id):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM share_template_elements WHERE template_id = ? ORDER BY id",
            (template_id,)
        ).fetchall()
        return jsonify([dict(r) for r in rows])


# ========== Share Templates API ==========
@app.route('/api/admin/share/templates', methods=['GET'])
@admin_required
def api_get_share_templates():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT t.*, b.name as bg_name, s.name as style_name, w.name as wm_name
            FROM share_templates t
            LEFT JOIN share_backgrounds b ON t.background_id = b.id
            LEFT JOIN share_text_styles s ON t.text_style_id = s.id
            LEFT JOIN share_watermarks w ON t.watermark_id = w.id
            ORDER BY t.created_at DESC
        """).fetchall()
        return jsonify([dict(r) for r in rows])

@app.route('/api/admin/share/templates', methods=['POST'])
@admin_required
@csrf_required
def api_create_share_template():
    data = request.json or {}
    name = data.get('name', 'Новый шаблон')
    background_id = data.get('background_id')
    text_style_id = data.get('text_style_id')
    watermark_id = data.get('watermark_id')
    is_default = data.get('is_default', 0)
    tariff = data.get('tariff', 'Искра')

    with get_db() as conn:
        conn.execute(
            """INSERT INTO share_templates (name, background_id, text_style_id, watermark_id, is_default, tariff)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, background_id, text_style_id, watermark_id, is_default, tariff)
        )
    return jsonify({"success": True})

@app.route('/api/admin/share/templates/<int:template_id>', methods=['DELETE'])
@admin_required
@csrf_required
def api_delete_share_template(template_id):
    with get_db() as conn:
        conn.execute("DELETE FROM share_templates WHERE id = ?", (template_id,))
    return jsonify({"success": True})

@app.route('/api/share/templates/public', methods=['GET'])
def api_get_public_templates():
    """Публичный список шаблонов для пользователей (без админ-ключа)."""
    tariff = request.args.get('tariff', 'Искра')
    
    with get_db() as conn:
        if tariff == 'Пламя':
            rows = conn.execute("""
                SELECT t.*, b.name as bg_name, s.name as style_name, w.name as wm_name
                FROM share_templates t
                LEFT JOIN share_backgrounds b ON t.background_id = b.id
                LEFT JOIN share_text_styles s ON t.text_style_id = s.id
                LEFT JOIN share_watermarks w ON t.watermark_id = w.id
                WHERE t.is_active = 1
                ORDER BY t.created_at DESC
            """).fetchall()
        elif tariff == 'Искра':
            rows = conn.execute("""
                SELECT t.*, b.name as bg_name, s.name as style_name, w.name as wm_name
                FROM share_templates t
                LEFT JOIN share_backgrounds b ON t.background_id = b.id
                LEFT JOIN share_text_styles s ON t.text_style_id = s.id
                LEFT JOIN share_watermarks w ON t.watermark_id = w.id
                WHERE t.is_active = 1 AND t.tariff IN ('Искра', 'Пламя')
                ORDER BY t.created_at DESC
            """).fetchall()
        else:
            rows = conn.execute("""
                SELECT t.*, b.name as bg_name, s.name as style_name, w.name as wm_name
                FROM share_templates t
                LEFT JOIN share_backgrounds b ON t.background_id = b.id
                LEFT JOIN share_text_styles s ON t.text_style_id = s.id
                LEFT JOIN share_watermarks w ON t.watermark_id = w.id
                WHERE t.is_active = 1 AND t.tariff = 'Искра'
                ORDER BY t.created_at DESC
            """).fetchall()
    
    return jsonify([dict(r) for r in rows])

# ========== Pages ==========
@app.route('/tarot/library')
def tarot_library_page():
    return render_template('tarot_library.html')

# ========== Error handlers ==========
@app.errorhandler(404)
def page_not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({"error": "Не найдено"}), 404
    return render_template('404.html'), 404

@app.errorhandler(HTTPException)
def handle_http_exception(e):
    # Обработчик именно для API — отдаём JSON; 404/500 уже перехвачены выше.
    if request.path.startswith('/api/'):
        return jsonify({"error": e.description or e.name or "Ошибка"}), e.code
    return e

@app.errorhandler(500)
def internal_error(e):
    import traceback
    add_log('ERROR', 'server', f"{e} | {traceback.format_exc()[:1000]}")
    if request.path.startswith('/api/'):
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500
    return render_template('500.html'), 500

# Кэширование статики
@app.after_request
def add_cache_header(response):
    if request.path.startswith('/static/'):
        if '.woff' in request.path or '.ttf' in request.path:
            response.cache_control.max_age = 31536000  # 1 год для шрифтов
        else:
            response.cache_control.max_age = 2592000  # 30 дней для остального
        response.cache_control.public = True
    return response

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000)