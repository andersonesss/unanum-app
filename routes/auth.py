# routes/auth.py
from flask import Blueprint, render_template, request, url_for, flash, session, jsonify
from utils.extensions import limiter
from database.db import get_db, add_log, USE_POSTGRES
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import json

from utils.auth_core import User, csrf_required, refresh_csrf_token
from utils.helpers import get_identifier, _migrate_guest_data, today_msk, now_msk

auth_bp = Blueprint('auth', __name__)

# ========== Главная ==========
@auth_bp.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@auth_bp.route('/logout', methods=['POST'])
@login_required
@csrf_required
def logout():
    add_log('INFO', 'auth', f"Выход: {current_user.email}")
    logout_user()
    flash('Ты всегда можешь вернуться. Мы ждём тебя.', 'info')
    return jsonify({"success": True, "redirect": url_for('auth.index')})

# ========== Profile API ==========
@auth_bp.route('/api/profile/data', methods=['GET'])
@login_required
def api_get_profile():
    return jsonify({
        "name": current_user.name or '',
        "email": current_user.email,
        "phone": current_user.phone or '',
        "birth_date": current_user.birth_date or '',
        "gender": current_user.gender or '',
        "avatar": current_user.avatar or '',
    })

@auth_bp.route('/api/profile/update', methods=['POST'])
@login_required
@csrf_required
def api_update_profile():
    data = request.json or {}
    avatar = data.get('avatar', '')
    if avatar:
        if not avatar.startswith('data:image/'):
            return jsonify({"error": "Недопустимый формат аватара"}), 400
        header, encoded = avatar.split(',', 1)
        mime_type = header.split(';')[0].split(':')[1]
        if mime_type not in ('image/png', 'image/jpeg', 'image/webp'):
            return jsonify({"error": "Разрешены только PNG, JPEG, WebP"}), 400
        import base64, io
        from PIL import Image
        try:
            img_data = base64.b64decode(encoded)
            if len(img_data) > 1 * 1024 * 1024:
                return jsonify({"error": "Размер аватара не более 1 МБ"}), 400
            img = Image.open(io.BytesIO(img_data))
            img.verify()
        except Exception:
            return jsonify({"error": "Повреждённое изображение"}), 400

    with get_db() as conn:
        # Обновляем всё кроме телефона (телефон задаётся при регистрации и не меняется)
        conn.execute(
            """UPDATE users SET name = ?, birth_date = ?, gender = ?, avatar = ? WHERE email = ?""",
            (data.get('name', ''), data.get('birth_date', ''),
             data.get('gender', ''), avatar, current_user.email)
        )
        conn.commit()

    current_user.name = data.get('name', '')
    current_user.birth_date = data.get('birth_date', '')
    current_user.gender = data.get('gender', '')
    current_user.avatar = avatar

    return jsonify({"success": True})

@auth_bp.route('/api/profile/change-password', methods=['POST'])
@login_required
@csrf_required
def api_change_password():
    data = request.json or {}
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')

    with get_db() as conn:
        user_row = conn.execute(
            "SELECT password_hash FROM users WHERE email = ?", (current_user.email,)
        ).fetchone()

        if not user_row:
            return jsonify({"error": "Пользователь не найден"}), 404

        if check_password_hash(user_row['password_hash'], old_password):
            new_hash = generate_password_hash(new_password)
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE email = ?",
                (new_hash, current_user.email)
            )
            conn.commit()
            add_log('INFO', 'auth', f"Смена пароля: {current_user.email}")
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Неверный старый пароль"}), 400

@auth_bp.route('/api/profile/delete', methods=['POST'])
@login_required
@csrf_required
def api_delete_account():
    """Удаление аккаунта и всех связанных данных."""
    data = request.json or {}
    password = data.get('password', '')
    
    if not password:
        return jsonify({"error": "Введите пароль для подтверждения"}), 400
    
    with get_db() as conn:
        user_row = conn.execute(
            "SELECT password_hash FROM users WHERE email = ?", (current_user.email,)
        ).fetchone()
        
        if not user_row or not check_password_hash(user_row['password_hash'], password):
            return jsonify({"error": "Неверный пароль"}), 400
        
        # Удаляем все данные пользователя
        conn.execute("DELETE FROM daily_cards WHERE identifier = ?", (current_user.email,))
        conn.execute("DELETE FROM daily_insights WHERE user_id = ?", (current_user.email,))
        conn.execute("DELETE FROM diary WHERE user_id = ?", (current_user.email,))
        conn.execute("DELETE FROM spreads WHERE user_id = ?", (current_user.email,))
        conn.execute("DELETE FROM horoscope_questions WHERE user_id = ?", (current_user.email,))
        conn.execute("DELETE FROM partners WHERE user_id = ?", (current_user.email,))
        conn.execute("DELETE FROM people WHERE user_id = ?", (current_user.email,))
        conn.execute("DELETE FROM user_portrait WHERE user_id = ?", (current_user.email,))
        conn.execute("DELETE FROM numer_memory WHERE user_id = ?", (current_user.email,))
        conn.execute("DELETE FROM user_events WHERE user_id = ?", (current_user.email,))
        conn.execute("DELETE FROM users WHERE email = ?", (current_user.email,))
        conn.commit()
    
    add_log('INFO', 'auth', f"Аккаунт удалён: {current_user.email}")
    logout_user()
    
    return jsonify({"success": True, "message": "Аккаунт удалён"})

# ========== Partner & People API ==========
@auth_bp.route('/api/profile/partner', methods=['GET'])
@login_required
def api_get_partner():
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM partners WHERE user_id = ? LIMIT 1",
            (current_user.email,)
        ).fetchone()
        if row:
            return jsonify(dict(row))
        return jsonify({})

@auth_bp.route('/api/profile/partner', methods=['POST'])
@login_required
@csrf_required
def api_save_partner():
    data = request.json or {}
    with get_db() as conn:
        existing = conn.execute(
            "SELECT * FROM partners WHERE user_id = ?", (current_user.email,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE partners SET name = ?, birth_date = ?, gender = ?, zodiac = ? WHERE user_id = ?""",
                (data.get('name', ''), data.get('birth_date', ''), data.get('gender', ''),
                 data.get('zodiac', ''), current_user.email)
            )
        else:
            conn.execute(
                """INSERT INTO partners (user_id, name, birth_date, gender, zodiac) VALUES (?, ?, ?, ?, ?)""",
                (current_user.email, data.get('name', ''), data.get('birth_date', ''),
                 data.get('gender', ''), data.get('zodiac', ''))
            )
        conn.commit()
    return jsonify({"success": True})

@auth_bp.route('/api/profile/people', methods=['GET'])
@login_required
def api_get_people():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM people WHERE user_id = ? ORDER BY id DESC",
            (current_user.email,)
        ).fetchall()
        return jsonify([dict(r) for r in rows])

@auth_bp.route('/api/profile/people', methods=['POST'])
@login_required
@csrf_required
def api_add_person():
    data = request.json or {}
    with get_db() as conn:
        # Серверная проверка лимита: до 10 человек на пользователя (тариф «Пламя»).
        # Клиентская проверка в profile.html есть, но она обходится.
        count_row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM people WHERE user_id = ?",
            (current_user.email,)
        ).fetchone()
        if count_row and count_row['cnt'] >= 10:
            return jsonify({"error": "Можно сохранить не более 10 человек."}), 400

        conn.execute(
            """INSERT INTO people (user_id, name, role, birth_date, zodiac, abbreviation) VALUES (?, ?, ?, ?, ?, ?)""",
            (current_user.email, data.get('name', ''), data.get('role', ''),
             data.get('birth_date', ''), data.get('zodiac', ''), data.get('abbreviation', ''))
        )
        conn.commit()
    return jsonify({"success": True})

@auth_bp.route('/api/profile/people/<int:person_id>', methods=['DELETE'])
@login_required
@csrf_required
def api_delete_person(person_id):
    with get_db() as conn:
        conn.execute("DELETE FROM people WHERE id = ? AND user_id = ?", (person_id, current_user.email))
        conn.commit()
    return jsonify({"success": True})

# ========== Diary & Spreads ==========
@auth_bp.route('/api/profile/diary', methods=['GET'])
@login_required
def api_get_diary():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM diary WHERE user_id = ? ORDER BY entry_date DESC LIMIT 30",
            (current_user.email,)
        ).fetchall()
        entries = [dict(r) for r in rows]
    return jsonify(entries)

@auth_bp.route('/api/profile/diary', methods=['POST'])
@login_required
@csrf_required
def api_add_diary():
    data = request.json or {}
    date_str = data.get('date', '')

    # Валидация: дата обязательна, формат YYYY-MM-DD, не в будущем (MSK).
    from datetime import datetime as _dt
    if not date_str:
        return jsonify({"error": "Укажите дату"}), 400
    try:
        dt_check = _dt.strptime(date_str, '%Y-%m-%d')
    except (ValueError, TypeError):
        return jsonify({"error": "Неверный формат даты"}), 400
    if dt_check > now_msk().replace(tzinfo=None):
        return jsonify({"error": "Дата не может быть в будущем"}), 400

    with get_db() as conn:
        conn.execute(
            "INSERT INTO diary (user_id, entry_date, mood, cards, notes) VALUES (?, ?, ?, ?, ?)",
            (current_user.email, date_str, data.get('mood', ''),
             data.get('cards', ''), data.get('notes', ''))
        )
        conn.commit()
    add_log('INFO', 'diary', f"Запись дневника от {date_str}")
    return jsonify({"success": True})

@auth_bp.route('/api/profile/spreads', methods=['GET'])
@login_required
def api_get_spreads():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM spreads WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
            (current_user.email,)
        ).fetchall()
        spreads = []
        for r in rows:
            s = dict(r)
            try:
                s['cards_data'] = json.loads(s['cards_data'])
            except:
                pass
            spreads.append(s)
    return jsonify(spreads)

# ========== User Profile (interests) ==========
@auth_bp.route('/api/user-profile', methods=['GET'])
def api_get_user_profile():
    identifier = get_identifier()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT tags_json FROM daily_insights WHERE user_id = ?",
            (identifier,)
        ).fetchall()

    tag_counts = {}
    for row in rows:
        row_tags = json.loads(row['tags_json'])
        for tag in row_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    dominant = max(tag_counts, key=tag_counts.get) if tag_counts else None
    return jsonify({
        "tag_counts": tag_counts,
        "dominant_tag": dominant
    })

# ========== Daily Questions ==========
@auth_bp.route('/api/daily-questions', methods=['GET'])
def api_get_daily_questions():
    today = today_msk()
    with get_db() as conn:
        row = conn.execute(
            "SELECT questions_json FROM daily_questions WHERE question_date = ?",
            (today,)
        ).fetchone()
        if row:
            return jsonify({"questions": json.loads(row['questions_json'])})

    from utils.ai_service import generate_daily_questions
    questions = generate_daily_questions()
    if not questions:
        questions = [
            {
                "question": "Если бы вы были луной сегодня, то какой?",
                "answers": [
                    {"text": "Таинственной и скрытной", "tags": ["spiritual"]},
                    {"text": "Любопытной и растущей", "tags": ["career"]},
                    {"text": "Яркой и заметной", "tags": ["love"]},
                    {"text": "Уставшей, но мудрой", "tags": ["health"]}
                ]
            },
            {
                "question": "Что из этого вы откладываете уже месяц?",
                "answers": [
                    {"text": "Стрижку", "tags": ["health"]},
                    {"text": "Важный разговор", "tags": ["love"]},
                    {"text": "Обучение", "tags": ["career"]},
                    {"text": "Финансовый план", "tags": ["finance"]}
                ]
            },
            {
                "question": "Ваша суперсила сегодня?",
                "answers": [
                    {"text": "Убеждение", "tags": ["career"]},
                    {"text": "Интуиция", "tags": ["spiritual"]},
                    {"text": "Решительность", "tags": ["finance"]},
                    {"text": "Лёгкость", "tags": ["love"]}
                ]
            }
        ]

    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO daily_questions (question_date, questions_json) VALUES (?, ?)",
            (today, json.dumps(questions, ensure_ascii=False))
        )
        conn.commit()
    return jsonify({"questions": questions})

@auth_bp.route('/api/daily-insights/today', methods=['GET'])
def api_check_today_insight():
    identifier = get_identifier()
    today = today_msk()
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM daily_insights WHERE user_id = ? AND insight_date = ?",
            (identifier, today)
        ).fetchone()
        return jsonify({"completed": row is not None})

@auth_bp.route('/api/daily-insights', methods=['POST'])
@csrf_required
def api_save_daily_insight():
    data = request.json or {}
    answers = data.get('answers', [])
    if not answers:
        return jsonify({"error": "Нет ответов"}), 400

    identifier = get_identifier()
    today = today_msk()
    tags = []
    for ans in answers:
        tags.extend(ans.get('tags', []))

    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO daily_insights (user_id, insight_date, answers_json, tags_json)
               VALUES (?, ?, ?, ?)""",
            (identifier, today, json.dumps(answers, ensure_ascii=False),
             json.dumps(tags, ensure_ascii=False))
        )
        conn.commit()
    return jsonify({"success": True, "tags": tags})

# ========== Tracking API ==========
@auth_bp.route('/api/track', methods=['POST'])
@csrf_required
@limiter.limit("30 per minute")
def api_track():
    data = request.json or {}
    events = data.get('events', [])[:50]
    if not events:
        return jsonify({"success": True})
    identifier = get_identifier()
    with get_db() as conn:
        for event in events:
            # Ограничиваем длину пользовательских строк — защита от забивания БД
            event_type = str(event.get('type', 'unknown'))[:50]
            section = str(event.get('section', ''))[:50]
            metadata = event.get('metadata', {})
            # Ограничиваем размер metadata: сериализуем и обрезаем
            metadata_json = json.dumps(metadata, ensure_ascii=False)[:2000]
            conn.execute(
                """INSERT INTO user_events (user_id, event_type, section, metadata)
                   VALUES (?, ?, ?, ?)""",
                (
                    identifier,
                    event_type,
                    section,
                    metadata_json
                )
            )
        conn.commit()
    return jsonify({"success": True})


# ========== Правовые страницы ==========
@auth_bp.route('/privacy')
def privacy_page():
    return render_template('privacy.html')

@auth_bp.route('/cookies')
def cookies_page():
    return render_template('cookies.html')

@auth_bp.route('/terms')
def terms_page():
    return render_template('terms.html')

@auth_bp.route('/offer')
def offer_page():
    return render_template('offer.html')

@auth_bp.route('/contacts')
def contacts_page():
    return render_template('contacts.html')

@auth_bp.route('/tariffs')
def tariffs_page():
    return render_template('tariffs.html')

# ========== Pages ==========
@auth_bp.route('/profile')
@login_required
def diary():
    return render_template('diary.html')

@auth_bp.route('/profile/settings')
@login_required
def profile_settings():
    return render_template('profile.html')

# ========== НОВАЯ АВТОРИЗАЦИЯ ЧЕРЕЗ ТЕЛЕФОН ==========

@auth_bp.route('/api/auth/request-call', methods=['POST'])
@csrf_required
@limiter.limit("1 per minute;3 per hour")
def api_request_call():
    """Заглушка для запроса звонка верификации."""
    data = request.json or {}
    phone = data.get('phone', '').strip()
    
    if not phone or len(phone) < 10:
        return jsonify({"success": False, "error": "Введите корректный номер телефона"}), 400
    
    # ЗАГЛУШКА: в будущем здесь будет вызов zvonok.com API
    # Сохраняем код в сессии для проверки
    code = '1234'
    session['phone_verification_code'] = code
    session['phone_verification_phone'] = phone
    
    add_log('INFO', 'auth', f"Запрошен звонок верификации на {phone} (заглушка, код: {code})")
    
    return jsonify({"success": True, "message": "Звонок совершён"})


@auth_bp.route('/api/auth/register', methods=['POST'])
@csrf_required
@limiter.limit("3 per minute;10 per hour")
def api_register():
    """Регистрация с проверкой кода и паролем."""
    data = request.json or {}
    phone = data.get('phone', '').strip()
    code = data.get('code', '').strip()
    password = data.get('password', '').strip()
    
    # Проверка телефона
    if not phone or len(phone) < 10:
        return jsonify({"success": False, "error": "Введите корректный номер телефона"}), 400
    
    # Проверка кода
    saved_code = session.get('phone_verification_code')
    saved_phone = session.get('phone_verification_phone')
    
    if not saved_code or not saved_phone:
        return jsonify({"success": False, "error": "Сначала запросите звонок для верификации"}), 400
    
    if phone != saved_phone or code != saved_code:
        return jsonify({"success": False, "error": "Неверный код верификации"}), 400
    
    # Валидация пароля
    if len(password) < 8:
        return jsonify({"success": False, "error": "Пароль должен быть не менее 8 символов"}), 400
    if not password[0].isupper():
        return jsonify({"success": False, "error": "Первая буква пароля должна быть заглавной"}), 400
    if not password[-1].isdigit():
        return jsonify({"success": False, "error": "Пароль должен заканчиваться цифрами"}), 400
    
    with get_db() as conn:
        # Проверяем, не занят ли телефон
        existing = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
        if existing:
            return jsonify({"success": False, "error": "Этот телефон уже зарегистрирован"}), 400
        
        # Создаём пользователя
        name = data.get('name', '').strip()
        birth_date = data.get('birth_date', '').strip()
        email = f"{phone}@numer.app"
        conn.execute(
            "INSERT INTO users (email, password_hash, phone, name, birth_date, subscription) VALUES (?, ?, ?, ?, ?, ?)",
            (email, generate_password_hash(password), phone, name, birth_date, 'Искра')
        )
        conn.commit()
        
        user_row = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
        user = User(dict(user_row))
        
        # ВАЖНО: считываем guest_id ДО login_user(), иначе get_identifier() вернёт email
        guest_identifier = get_identifier()
        
        login_user(user)
        refresh_csrf_token()
        
        if name or birth_date:
            from utils.orchestrator import update_portrait_from_init
            update_portrait_from_init(email, {'name': name, 'birth_date': birth_date})
        
        # Перенос гостевых данных (guest_identifier зафиксирован до login).
        # В SQLite conn.__exit__ НЕ делает commit — добавляем явно.
        # В PG PgWrapper.__exit__ коммитит сам, но повторный commit() безвреден.
        if guest_identifier.startswith('guest:'):
            _migrate_guest_data(conn, guest_identifier, email)
            conn.commit()
    
    # Очищаем сессию
    session.pop('phone_verification_code', None)
    session.pop('phone_verification_phone', None)
    session['show_onboarding'] = True
    
    # Логируем согласия
    try:
        with get_db() as log_conn:
            if USE_POSTGRES:
                cur = log_conn.cursor()
                cur.execute(
                    "INSERT INTO consent_logs (user_id, consent_type, ip_address) VALUES (%s, %s, %s)",
                    (email, 'data_processing', request.remote_addr)
                )
                cur.execute(
                    "INSERT INTO consent_logs (user_id, consent_type, ip_address) VALUES (%s, %s, %s)",
                    (email, 'cross_border_transfer', request.remote_addr)
                )
                log_conn.commit()
            else:
                log_conn.execute(
                    "INSERT INTO consent_logs (user_id, consent_type, ip_address) VALUES (?, ?, ?)",
                    (email, 'data_processing', request.remote_addr)
                )
                log_conn.execute(
                    "INSERT INTO consent_logs (user_id, consent_type, ip_address) VALUES (?, ?, ?)",
                    (email, 'cross_border_transfer', request.remote_addr)
                )
                log_conn.commit()
    except Exception as e:
        add_log('ERROR', 'auth', f"Ошибка записи согласия: {e}")
    
    add_log('INFO', 'auth', f"Регистрация через телефон: {phone}")
    
    return jsonify({"success": True, "message": "Регистрация успешна"})


@auth_bp.route('/api/auth/login', methods=['POST'])
@csrf_required
@limiter.limit("5 per minute;20 per hour")
def api_login():
    """Вход по телефону и паролю."""
    data = request.json or {}
    phone = data.get('phone', '').strip()
    password = data.get('password', '').strip()
    
    if not phone or not password:
        return jsonify({"success": False, "error": "Введите телефон и пароль"}), 400
    
    with get_db() as conn:
        user_row = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
        if not user_row:
            return jsonify({"success": False, "error": "Неверный телефон или пароль"}), 401
        
        if not check_password_hash(user_row['password_hash'], password):
            return jsonify({"success": False, "error": "Неверный телефон или пароль"}), 401
        
        user = User(dict(user_row))
        
        # ВАЖНО: считываем guest_id ДО login_user(), иначе get_identifier() вернёт email
        guest_identifier = get_identifier()
        
        login_user(user)
        refresh_csrf_token()
        
        # См. комментарий в api_register — в SQLite commit нужен явно.
        if guest_identifier.startswith('guest:'):
            _migrate_guest_data(conn, guest_identifier, user.email)
            conn.commit()
    
    session['show_onboarding'] = True
    add_log('INFO', 'auth', f"Вход через телефон: {phone}")
    
    return jsonify({"success": True, "message": "Вход выполнен"})

@auth_bp.route('/api/numer/check-limit', methods=['GET'])
@limiter.limit("10 per minute")
def api_check_numer_limit():
    """Проверяет, может ли пользователь задать вопрос."""
    identifier = get_identifier()
    today = today_msk()
    
    if current_user.is_authenticated:
        if current_user.subscription == 'Пламя':
            return jsonify({"can_ask": True, "limit": None, "remaining": "безлимит"})
        else:
            limit = 3
        user_id = current_user.email
    else:
        limit = 1
        user_id = identifier
    
    with get_db() as conn:
        if USE_POSTGRES:
            # Диапазон МСК-суток в timestamptz — PG использует индекс по created_at.
            from datetime import datetime as _dt, timedelta as _td
            _start_msk = _dt.strptime(today, '%Y-%m-%d')
            _end_msk = _start_msk + _td(days=1)
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM numer_memory "
                "WHERE user_id = ? AND type = 'dialogue' "
                "AND created_at >= ?::timestamptz AT TIME ZONE 'Europe/Moscow' "
                "AND created_at <  ?::timestamptz AT TIME ZONE 'Europe/Moscow'",
                (user_id, _start_msk.isoformat(), _end_msk.isoformat())
            ).fetchone()
        else:
            # SQLite: диапазон [начало МСК, конец МСК) в UTC — позволяет использовать индекс.
            from datetime import datetime as _dt, timedelta as _td
            _start_utc = (_dt.strptime(today, '%Y-%m-%d') - _td(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
            _end_utc = (_dt.strptime(today, '%Y-%m-%d') + _td(days=1) - _td(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM numer_memory "
                "WHERE user_id = ? AND type = 'dialogue' "
                "AND created_at >= ? AND created_at < ?",
                (user_id, _start_utc, _end_utc)
            ).fetchone()
        count = row['cnt'] if row else 0
    
    remaining = max(0, limit - count)
    can_ask = remaining > 0
    
    return jsonify({
        "can_ask": can_ask,
        "limit": limit,
        "remaining": remaining,
        "asked_today": count
    })

@auth_bp.route('/api/profile/people/<int:person_id>/update', methods=['POST'])
@login_required
@csrf_required
def api_update_person(person_id):
    data = request.json or {}
    with get_db() as conn:
        result = conn.execute(
            """UPDATE people SET name = ?, role = ?, birth_date = ?, zodiac = ? WHERE id = ? AND user_id = ?""",
            (data.get('name', ''), data.get('role', ''), data.get('birth_date', ''),
             data.get('zodiac', ''), person_id, current_user.email)
        )
        # PgWrapper отдаёт rowcount через total_changes (self._cur.rowcount);
        # sqlite3.Cursor — через rowcount.
        rowcount = result.total_changes if hasattr(result, 'total_changes') else result.rowcount
        conn.commit()
    if rowcount == 0:
        return jsonify({"error": "Человек не найден"}), 404
    return jsonify({"success": True})