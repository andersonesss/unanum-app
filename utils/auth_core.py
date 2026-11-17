# utils/auth_core.py
import secrets
from functools import wraps
from flask import session, jsonify, request
from flask_login import LoginManager, UserMixin

login_manager = LoginManager()
login_manager.login_view = 'auth.index'
login_manager.login_message = 'Пожалуйста, войдите, чтобы получить полный доступ.'

class User(UserMixin):
    def __init__(self, row_dict):
        self.id = row_dict['email']
        self.email = row_dict['email']
        self.name = row_dict.get('name', '')
        self.phone = row_dict.get('phone', '')
        self.birth_date = row_dict.get('birth_date', '')
        self.gender = row_dict.get('gender', '')
        self.avatar = row_dict.get('avatar', '')
        raw_sub = row_dict.get('subscription') or 'Искра'
        self.subscription = raw_sub if raw_sub in ('Искра', 'Пламя') else 'Искра'

    def get_question_limit(self):
        if self.subscription == 'Пламя':
            return None
        else:
            return 3

    def get_tariff_name(self):
        return self.subscription

@login_manager.user_loader
def load_user(user_id):
    from database.db import get_db
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (user_id,)).fetchone()
        if row:
            return User(dict(row))
    return None

def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def refresh_csrf_token():
    """Вызывать после логина/регистрации для защиты от session fixation."""
    session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def csrf_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            token = request.headers.get('X-CSRFToken') or request.form.get('_csrf_token')
            if not token or token != session.get('csrf_token'):
                return jsonify({"error": "CSRF token missing or invalid"}), 400
        return f(*args, **kwargs)
    return decorated