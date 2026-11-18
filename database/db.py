# database/db.py
import sqlite3
import os
from config import Config

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = Config.DATABASE_PATH

USE_POSTGRES = os.getenv("POSTGRES_HOST") is not None

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    from psycopg2 import pool

    _pg_pool = None

    def _get_pool():
        global _pg_pool
        if _pg_pool is None or _pg_pool.closed:
            _pg_pool = pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=10,
                host=Config.POSTGRES_HOST,
                port=Config.POSTGRES_PORT,
                dbname=Config.POSTGRES_DB,
                user=Config.POSTGRES_USER,
                password=Config.POSTGRES_PASSWORD,
            )
        return _pg_pool

    def get_db():
        pool_obj = _get_pool()
        conn = pool_obj.getconn()
        conn.autocommit = False
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        class PgWrapper:
            def __init__(self, pool_ref, conn, cur):
                self._pool = pool_ref
                self._conn = conn
                self._cur = cur
                self._closed = False
            
            def __enter__(self):
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                if self._closed:
                    return False
                self._closed = True
                try:
                    if exc_type is not None:
                        self._conn.rollback()
                    else:
                        self._conn.commit()
                finally:
                    self._cur.close()
                    self._pool.putconn(self._conn)
                return False
            
            def execute(self, sql, params=None):
                import re
                sql_pg = sql.replace('?', '%s')
                
                # INSERT OR IGNORE -> INSERT ... ON CONFLICT DO NOTHING
                if 'INSERT OR IGNORE' in sql_pg.upper():
                    sql_pg = sql_pg.replace('INSERT OR IGNORE', 'INSERT')
                    if 'ON CONFLICT' not in sql_pg.upper():
                        sql_pg += ' ON CONFLICT DO NOTHING'
                
                # INSERT OR REPLACE -> INSERT ... ON CONFLICT ... DO UPDATE (upsert)
                elif 'INSERT OR REPLACE' in sql_pg.upper():
                    sql_pg = sql_pg.replace('INSERT OR REPLACE INTO', 'INSERT INTO')
                    
                    if 'ON CONFLICT' not in sql_pg.upper():
                        # Пытаемся распознать таблицу и построить правильный ON CONFLICT
                        match = re.match(
                            r'INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)',
                            sql_pg, re.IGNORECASE
                        )
                        
                        table_map = {
                            'user_portrait': {
                                'conflict': '(user_id)',
                                'update': 'portrait_json = EXCLUDED.portrait_json, updated_at = EXCLUDED.updated_at'
                            },
                            'daily_insights': {
                                'conflict': '(user_id, insight_date)',
                                'update': 'answers_json = EXCLUDED.answers_json, tags_json = EXCLUDED.tags_json'
                            },
                            'daily_questions': {
                                'conflict': '(question_date)',
                                'update': 'questions_json = EXCLUDED.questions_json'
                            },
                            'daily_cards': {
                                'conflict': '(identifier, card_date)',
                                'update': 'card_id = EXCLUDED.card_id, is_reversed = EXCLUDED.is_reversed, ai_text = EXCLUDED.ai_text'
                            },
                            'ai_cache': {
                                'conflict': '(prompt_hash)',
                                'update': 'response = EXCLUDED.response'
                            },
                            'trial_tokens': {
                                'conflict': '(identifier)',
                                'update': 'spreads_used = EXCLUDED.spreads_used, max_spreads = EXCLUDED.max_spreads'
                            },
                            'users': {
                                'conflict': '(email)',
                                'update': "password_hash = EXCLUDED.password_hash, name = EXCLUDED.name, phone = EXCLUDED.phone, birth_date = EXCLUDED.birth_date, gender = EXCLUDED.gender, avatar = EXCLUDED.avatar, subscription = EXCLUDED.subscription"
                            },
                            'prompts': {
                                'conflict': '(name)',
                                'update': 'content = EXCLUDED.content, updated_at = EXCLUDED.updated_at'
                            },
                            'partners': {
                                'conflict': '(user_id)',
                                'update': "name = EXCLUDED.name, birth_date = EXCLUDED.birth_date, gender = EXCLUDED.gender, zodiac = EXCLUDED.zodiac"
                            },
                            'spreads': {
                                'conflict': '(id)',
                                'update': "spread_type = EXCLUDED.spread_type, question = EXCLUDED.question, cards_data = EXCLUDED.cards_data, ai_interpretation = EXCLUDED.ai_interpretation"
                            },
                            'diary': {
                                'conflict': '(id)',
                                'update': "entry_date = EXCLUDED.entry_date, mood = EXCLUDED.mood, cards = EXCLUDED.cards, notes = EXCLUDED.notes"
                            },
                            'horoscope_questions': {
                                'conflict': '(id)',
                                'update': "question_date = EXCLUDED.question_date, question = EXCLUDED.question, answer = EXCLUDED.answer, zodiac_sign = EXCLUDED.zodiac_sign, period = EXCLUDED.period"
                            },
                            'numer_memory': {
                                'conflict': '(id)',
                                'update': "type = EXCLUDED.type, content = EXCLUDED.content, metadata = EXCLUDED.metadata"
                            },
                            'user_events': {
                                'conflict': '(id)',
                                'update': "event_type = EXCLUDED.event_type, section = EXCLUDED.section, metadata = EXCLUDED.metadata"
                            },
                            'people': {
                                'conflict': '(id)',
                                'update': "name = EXCLUDED.name, role = EXCLUDED.role, birth_date = EXCLUDED.birth_date, zodiac = EXCLUDED.zodiac, abbreviation = EXCLUDED.abbreviation"
                            },
                            'share_backgrounds': {
                                'conflict': '(id)',
                                'update': "name = EXCLUDED.name, image_path = EXCLUDED.image_path, tariff = EXCLUDED.tariff, is_active = EXCLUDED.is_active"
                            },
                            'share_text_styles': {
                                'conflict': '(id)',
                                'update': "name = EXCLUDED.name, font_path = EXCLUDED.font_path, font_size_min = EXCLUDED.font_size_min, font_size_max = EXCLUDED.font_size_max, color = EXCLUDED.color, align = EXCLUDED.align, shadow_color = EXCLUDED.shadow_color, shadow_offset = EXCLUDED.shadow_offset, shadow_blur = EXCLUDED.shadow_blur, text_shape = EXCLUDED.text_shape, tariff = EXCLUDED.tariff, is_active = EXCLUDED.is_active"
                            },
                            'share_watermarks': {
                                'conflict': '(id)',
                                'update': "name = EXCLUDED.name, image_path = EXCLUDED.image_path, position = EXCLUDED.position, size = EXCLUDED.size, pos_x = EXCLUDED.pos_x, pos_y = EXCLUDED.pos_y, size_percent = EXCLUDED.size_percent, tariff = EXCLUDED.tariff, is_active = EXCLUDED.is_active"
                            },
                            'share_templates': {
                                'conflict': '(id)',
                                'update': "name = EXCLUDED.name, background_id = EXCLUDED.background_id, text_style_id = EXCLUDED.text_style_id, watermark_id = EXCLUDED.watermark_id, is_default = EXCLUDED.is_default, tariff = EXCLUDED.tariff, is_active = EXCLUDED.is_active"
                            },
                            'share_template_elements': {
                                'conflict': '(id)',
                                'update': "type = EXCLUDED.type, text = EXCLUDED.text, color = EXCLUDED.color, shape = EXCLUDED.shape, font_size = EXCLUDED.font_size, placeholder = EXCLUDED.placeholder, x1 = EXCLUDED.x1, y1 = EXCLUDED.y1, x2 = EXCLUDED.x2, y2 = EXCLUDED.y2, x3 = EXCLUDED.x3, y3 = EXCLUDED.y3, x4 = EXCLUDED.x4, y4 = EXCLUDED.y4"
                            },
                            'consent_logs': {
                                'conflict': '(id)',
                                'update': "user_id = EXCLUDED.user_id, consent_type = EXCLUDED.consent_type, ip_address = EXCLUDED.ip_address, privacy_version = EXCLUDED.privacy_version"
                            },
                            'logs': {
                                'conflict': '(id)',
                                'update': "level = EXCLUDED.level, source = EXCLUDED.source, message = EXCLUDED.message"
                            },
                        }
                        
                        if match and match.group(1) in table_map:
                            tbl = table_map[match.group(1)]
                            sql_pg += f' ON CONFLICT {tbl["conflict"]} DO UPDATE SET {tbl["update"]}'
                        else:
                            # Таблица не в table_map — это ошибка разработчика:
                            # при конфликте данные не обновятся (ON CONFLICT DO NOTHING).
                            # Громко логируем и бросаем, чтобы не терять данные тихо.
                            import logging
                            table_name = match.group(1) if match else '?'
                            logging.error(
                                f"PgWrapper: 'INSERT OR REPLACE' для таблицы '{table_name}' "
                                f"не найден в table_map. Добавьте запись conflict/update "
                                f"или используйте обычный INSERT с явным ON CONFLICT."
                            )
                            raise RuntimeError(
                                f"table_map не содержит запись для '{table_name}' "
                                f"(INSERT OR REPLACE в PG требует явного conflict/update)"
                            )
                
                if params:
                    self._cur.execute(sql_pg, params)
                else:
                    self._cur.execute(sql_pg)
                return self
            
            def fetchone(self):
                return self._cur.fetchone()
            
            def fetchall(self):
                return self._cur.fetchall()
            
            def commit(self):
                self._conn.commit()
            
            def rollback(self):
                self._conn.rollback()
            
            def cursor(self):
                return self._cur
            
            @property
            def total_changes(self):
                return self._cur.rowcount
            
            def close(self):
                pass
        
        return PgWrapper(_pg_pool, conn, cur)

else:
    USE_POSTGRES = False
    
    def get_db():
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn


def init_db():
    if USE_POSTGRES:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    name TEXT DEFAULT '',
                    phone TEXT DEFAULT '',
                    birth_date TEXT DEFAULT '',
                    gender TEXT DEFAULT '',
                    avatar TEXT DEFAULT '',
                    subscription TEXT DEFAULT 'Искра',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # Миграция subscription ДО UPDATE: на старой БД без этой колонки
            # CREATE TABLE IF NOT EXISTS не добавит её, а UPDATE упадёт
            # с UndefinedColumn и уронит init_db().
            try:
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription TEXT DEFAULT 'Искра'")
            except Exception:
                pass
            cur.execute("""
                UPDATE users SET subscription = 'Искра'
                WHERE subscription NOT IN ('Искра', 'Пламя') OR subscription IS NULL
            """)
            # Миграции: колонки, добавленные в новых версиях
            for col_sql in [
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT DEFAULT ''",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS birth_date TEXT DEFAULT ''",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS gender TEXT DEFAULT ''",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar TEXT DEFAULT ''",
            ]:
                try:
                    cur.execute(col_sql)
                except Exception:
                    pass
            cur.execute("""
                CREATE TABLE IF NOT EXISTS spreads (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT DEFAULT '',
                    spread_type TEXT NOT NULL,
                    question TEXT DEFAULT '',
                    cards_data TEXT NOT NULL,
                    ai_interpretation TEXT DEFAULT '',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS diary (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    entry_date DATE NOT NULL,
                    mood TEXT DEFAULT '',
                    cards TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ai_cache (
                    id SERIAL PRIMARY KEY,
                    prompt_hash TEXT UNIQUE NOT NULL,
                    response TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id SERIAL PRIMARY KEY,
                    level TEXT DEFAULT 'INFO',
                    source TEXT DEFAULT 'system',
                    message TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trial_tokens (
                    id SERIAL PRIMARY KEY,
                    identifier TEXT UNIQUE NOT NULL,
                    spreads_used INTEGER DEFAULT 0,
                    max_spreads INTEGER DEFAULT 1,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_cards (
                    id SERIAL PRIMARY KEY,
                    identifier TEXT NOT NULL,
                    card_date DATE NOT NULL,
                    card_id INTEGER NOT NULL,
                    is_reversed INTEGER DEFAULT 0,
                    ai_text TEXT DEFAULT '',
                    UNIQUE(identifier, card_date)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS prompts (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    content TEXT NOT NULL,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS horoscope_questions (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    question_date DATE NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT DEFAULT '',
                    zodiac_sign TEXT DEFAULT '',
                    period TEXT DEFAULT 'день',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS partners (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL UNIQUE,
                    name TEXT DEFAULT '',
                    birth_date TEXT DEFAULT '',
                    gender TEXT DEFAULT '',
                    zodiac TEXT DEFAULT ''
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS people (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT DEFAULT '',
                    role TEXT DEFAULT '',
                    birth_date TEXT DEFAULT '',
                    zodiac TEXT DEFAULT '',
                    abbreviation TEXT DEFAULT ''
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_portrait (
                    user_id TEXT PRIMARY KEY,
                    portrait_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS numer_memory (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    type TEXT NOT NULL DEFAULT 'dialogue',
                    content TEXT NOT NULL DEFAULT '',
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_events (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    section TEXT DEFAULT '',
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            for idx_sql in [
                "CREATE INDEX IF NOT EXISTS idx_daily_cards_identifier_date ON daily_cards(identifier, card_date)",
                "CREATE INDEX IF NOT EXISTS idx_user_events_user_id ON user_events(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_user_events_created_at ON user_events(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_horoscope_questions_user_date ON horoscope_questions(user_id, question_date)",
                "CREATE INDEX IF NOT EXISTS idx_ai_cache_hash ON ai_cache(prompt_hash)",
                "CREATE INDEX IF NOT EXISTS idx_ai_cache_created_at ON ai_cache(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_spreads_user ON spreads(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_diary_user_date ON diary(user_id, entry_date)",
                "CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_numer_memory_user_id ON numer_memory(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_numer_memory_created_at ON numer_memory(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_numer_memory_user_type_created ON numer_memory(user_id, type, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_people_user_id ON people(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)",
            ]:
                try:
                    cur.execute(idx_sql)
                except:
                    pass

            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_questions (
                    id SERIAL PRIMARY KEY,
                    question_date DATE UNIQUE NOT NULL,
                    questions_json TEXT NOT NULL,
                    generated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_insights (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    insight_date DATE NOT NULL,
                    answers_json TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(user_id, insight_date)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS share_backgrounds (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    tariff TEXT NOT NULL DEFAULT 'Искра',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS share_text_styles (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    font_path TEXT DEFAULT '',
                    font_size_min INTEGER DEFAULT 32,
                    font_size_max INTEGER DEFAULT 60,
                    color TEXT DEFAULT '#ffffff',
                    align TEXT DEFAULT 'center',
                    shadow_color TEXT DEFAULT '#000000',
                    shadow_offset TEXT DEFAULT '2,2',
                    shadow_blur INTEGER DEFAULT 4,
                    text_shape TEXT DEFAULT 'rectangle',
                    tariff TEXT NOT NULL DEFAULT 'Искра',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                ALTER TABLE share_text_styles ADD COLUMN IF NOT EXISTS text_shape TEXT DEFAULT 'rectangle'
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS share_watermarks (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    position TEXT DEFAULT 'bottom-right',
                    size TEXT DEFAULT '200x60',
                    pos_x INTEGER DEFAULT 40,
                    pos_y INTEGER DEFAULT 1660,
                    size_percent INTEGER DEFAULT 20,
                    tariff TEXT NOT NULL DEFAULT 'Искра',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            for col_sql in [
                "ALTER TABLE share_watermarks ADD COLUMN IF NOT EXISTS pos_x INTEGER DEFAULT 40",
                "ALTER TABLE share_watermarks ADD COLUMN IF NOT EXISTS pos_y INTEGER DEFAULT 1660",
                "ALTER TABLE share_watermarks ADD COLUMN IF NOT EXISTS size_percent INTEGER DEFAULT 20",
            ]:
                try:
                    cur.execute(col_sql)
                except Exception:
                    pass
            cur.execute("""
                CREATE TABLE IF NOT EXISTS share_templates (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    background_id INTEGER,
                    text_style_id INTEGER,
                    watermark_id INTEGER,
                    is_default INTEGER DEFAULT 0,
                    tariff TEXT NOT NULL DEFAULT 'Искра',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    FOREIGN KEY (background_id) REFERENCES share_backgrounds(id) ON DELETE SET NULL,
                    FOREIGN KEY (text_style_id) REFERENCES share_text_styles(id) ON DELETE SET NULL,
                    FOREIGN KEY (watermark_id) REFERENCES share_watermarks(id) ON DELETE SET NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS consent_logs (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    consent_type TEXT NOT NULL,
                    ip_address TEXT DEFAULT '',
                    privacy_version TEXT DEFAULT '2026-07-11',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS share_template_elements (
                    id SERIAL PRIMARY KEY,
                    template_id INTEGER NOT NULL,
                    type TEXT NOT NULL DEFAULT 'text',
                    text TEXT DEFAULT '',
                    color TEXT DEFAULT '#ffd54f',
                    shape TEXT DEFAULT 'free',
                    font_size INTEGER DEFAULT 24,
                    placeholder INTEGER DEFAULT 0,
                    image_path TEXT DEFAULT '',
                    x1 INTEGER DEFAULT 100, y1 INTEGER DEFAULT 300,
                    x2 INTEGER DEFAULT 260, y2 INTEGER DEFAULT 300,
                    x3 INTEGER DEFAULT 260, y3 INTEGER DEFAULT 360,
                    x4 INTEGER DEFAULT 100, y4 INTEGER DEFAULT 360,
                    FOREIGN KEY (template_id) REFERENCES share_templates(id) ON DELETE CASCADE
                )
            """)
            cur.execute("""
                ALTER TABLE share_template_elements ADD COLUMN IF NOT EXISTS placeholder INTEGER DEFAULT 0
            """)
            cur.execute("""
                ALTER TABLE share_template_elements ADD COLUMN IF NOT EXISTS image_path TEXT DEFAULT ''
            """)
            conn.commit()
            print("[OK] PostgreSQL инициализирована.")
    else:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        with get_db() as conn:
            c = conn.cursor()

            c.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    name TEXT DEFAULT '',
                    phone TEXT DEFAULT '',
                    birth_date TEXT DEFAULT '',
                    gender TEXT DEFAULT '',
                    avatar TEXT DEFAULT '',
                    subscription TEXT DEFAULT 'Искра',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Миграция subscription ДО UPDATE: на старой БД без этой колонки
            # CREATE TABLE IF NOT EXISTS не добавит её, а UPDATE упадёт
            # с "no such column: subscription" и уронит init_db().
            # SQLite не поддерживает ADD COLUMN IF NOT EXISTS — используем try/except,
            # как в соседнем цикле миграций ниже.
            try:
                c.execute("ALTER TABLE users ADD COLUMN subscription TEXT DEFAULT 'Искра'")
            except:
                pass

            c.execute("""
                UPDATE users SET subscription = 'Искра'
                WHERE subscription NOT IN ('Искра', 'Пламя') OR subscription IS NULL
            """)

            for col, col_type in [
                ('phone', "TEXT DEFAULT ''"),
                ('birth_date', "TEXT DEFAULT ''"),
                ('gender', "TEXT DEFAULT ''"),
                ('avatar', "TEXT DEFAULT ''"),
            ]:
                try:
                    c.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
                except:
                    pass

            c.execute("""
                CREATE TABLE IF NOT EXISTS spreads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT DEFAULT '',
                    spread_type TEXT NOT NULL,
                    question TEXT DEFAULT '',
                    cards_data TEXT NOT NULL,
                    ai_interpretation TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS diary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    entry_date DATE NOT NULL,
                    mood TEXT DEFAULT '',
                    cards TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS ai_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prompt_hash TEXT UNIQUE NOT NULL,
                    response TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT DEFAULT 'INFO',
                    source TEXT DEFAULT 'system',
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS trial_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    identifier TEXT UNIQUE NOT NULL,
                    spreads_used INTEGER DEFAULT 0,
                    max_spreads INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS daily_cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    identifier TEXT NOT NULL,
                    card_date DATE NOT NULL,
                    card_id INTEGER NOT NULL,
                    is_reversed INTEGER DEFAULT 0,
                    ai_text TEXT DEFAULT '',
                    UNIQUE(identifier, card_date)
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS prompts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    content TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS horoscope_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    question_date DATE NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT DEFAULT '',
                    zodiac_sign TEXT DEFAULT '',
                    period TEXT DEFAULT 'день',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS partners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL UNIQUE,
                    name TEXT DEFAULT '',
                    birth_date TEXT DEFAULT '',
                    gender TEXT DEFAULT '',
                    zodiac TEXT DEFAULT ''
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS people (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    name TEXT DEFAULT '',
                    role TEXT DEFAULT '',
                    birth_date TEXT DEFAULT '',
                    zodiac TEXT DEFAULT '',
                    abbreviation TEXT DEFAULT ''
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS user_portrait (
                    user_id TEXT PRIMARY KEY,
                    portrait_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS numer_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    type TEXT NOT NULL DEFAULT 'dialogue',
                    content TEXT NOT NULL DEFAULT '',
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS user_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    section TEXT DEFAULT '',
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            c.execute("CREATE INDEX IF NOT EXISTS idx_daily_cards_identifier_date ON daily_cards(identifier, card_date)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_user_events_user_id ON user_events(user_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_user_events_created_at ON user_events(created_at)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_horoscope_questions_user_date ON horoscope_questions(user_id, question_date)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_ai_cache_hash ON ai_cache(prompt_hash)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_ai_cache_created_at ON ai_cache(created_at)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_spreads_user ON spreads(user_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_diary_user_date ON diary(user_id, entry_date)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs(created_at)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_numer_memory_user_id ON numer_memory(user_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_numer_memory_created_at ON numer_memory(created_at)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_numer_memory_user_type_created ON numer_memory(user_id, type, created_at)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_people_user_id ON people(user_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)")

            c.execute("""
                CREATE TABLE IF NOT EXISTS daily_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_date DATE UNIQUE NOT NULL,
                    questions_json TEXT NOT NULL,
                    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS daily_insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    insight_date DATE NOT NULL,
                    answers_json TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, insight_date)
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS share_backgrounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    tariff TEXT NOT NULL DEFAULT 'Искра',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS share_text_styles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    font_path TEXT DEFAULT '',
                    font_size_min INTEGER DEFAULT 32,
                    font_size_max INTEGER DEFAULT 60,
                    color TEXT DEFAULT '#ffffff',
                    align TEXT DEFAULT 'center',
                    shadow_color TEXT DEFAULT '#000000',
                    shadow_offset TEXT DEFAULT '2,2',
                    shadow_blur INTEGER DEFAULT 4,
                    text_shape TEXT DEFAULT 'rectangle',
                    tariff TEXT NOT NULL DEFAULT 'Искра',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            for col, col_type in [
                ('text_shape', "TEXT DEFAULT 'rectangle'"),
            ]:
                try:
                    c.execute(f"ALTER TABLE share_text_styles ADD COLUMN {col} {col_type}")
                except:
                    pass

            c.execute("""
                CREATE TABLE IF NOT EXISTS consent_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    consent_type TEXT NOT NULL,
                    ip_address TEXT DEFAULT '',
                    privacy_version TEXT DEFAULT '2026-07-11',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS share_watermarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    position TEXT DEFAULT 'bottom-right',
                    size TEXT DEFAULT '200x60',
                    pos_x INTEGER DEFAULT 40,
                    pos_y INTEGER DEFAULT 1660,
                    size_percent INTEGER DEFAULT 20,
                    tariff TEXT NOT NULL DEFAULT 'Искра',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            for col, col_type in [
                ('pos_x', "INTEGER DEFAULT 40"),
                ('pos_y', "INTEGER DEFAULT 1660"),
                ('size_percent', "INTEGER DEFAULT 20"),
            ]:
                try:
                    c.execute(f"ALTER TABLE share_watermarks ADD COLUMN {col} {col_type}")
                except:
                    pass

            c.execute("""
                CREATE TABLE IF NOT EXISTS share_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    background_id INTEGER,
                    text_style_id INTEGER,
                    watermark_id INTEGER,
                    is_default INTEGER DEFAULT 0,
                    tariff TEXT NOT NULL DEFAULT 'Искра',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS share_template_elements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    type TEXT NOT NULL DEFAULT 'text',
                    text TEXT DEFAULT '',
                    color TEXT DEFAULT '#ffd54f',
                    shape TEXT DEFAULT 'free',
                    font_size INTEGER DEFAULT 24,
                    placeholder INTEGER DEFAULT 0,
                    image_path TEXT DEFAULT '',
                    x1 INTEGER DEFAULT 100, y1 INTEGER DEFAULT 300,
                    x2 INTEGER DEFAULT 260, y2 INTEGER DEFAULT 300,
                    x3 INTEGER DEFAULT 260, y3 INTEGER DEFAULT 360,
                    x4 INTEGER DEFAULT 100, y4 INTEGER DEFAULT 360
                )
            """)
            for col, col_type in [
                ('placeholder', "INTEGER DEFAULT 0"),
                ('image_path', "TEXT DEFAULT ''"),
            ]:
                try:
                    c.execute(f"ALTER TABLE share_template_elements ADD COLUMN {col} {col_type}")
                except:
                    pass

            conn.commit()
            print("[OK] База данных SQLite инициализирована.")

    seed_default_prompts()
    # Автоочистка старых записей кэша (TTL = 30 дней)
    try:
        cleanup_old_cache(max_age_days=30)
    except Exception:
        pass


def seed_default_prompts():
    import json
    try:
        with open(os.path.join(_BASE_DIR, 'data', 'default_prompts.json'), 'r', encoding='utf-8') as f:
            default_prompts = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[WARN] default_prompts.json не загружен ({e}). Промпты останутся пустыми.")
        return

    with get_db() as conn:
        if USE_POSTGRES:
            cur = conn.cursor()
            for prompt in default_prompts:
                cur.execute("""
                    INSERT INTO prompts (name, content) VALUES (%s, %s)
                    ON CONFLICT (name) DO NOTHING
                """, (prompt['name'], prompt['content']))
            conn.commit()
        else:
            c = conn.cursor()
            for prompt in default_prompts:
                c.execute("""
                    INSERT OR IGNORE INTO prompts (name, content) VALUES (?, ?)
                """, (prompt['name'], prompt['content']))
            conn.commit()

    # Создание тестового пользователя — только при явном SEED_TEST_USER=1
    # (по умолчанию выключено: тестовый пользователь в проде не нужен).
    if os.getenv('FLASK_ENV') == 'development' and os.getenv('SEED_TEST_USER') == '1':
        with get_db() as conn:
            from werkzeug.security import generate_password_hash
            test_phone = '9991234567'
            test_password = 'Test1234'
            
            if USE_POSTGRES:
                cur = conn.cursor()
                cur.execute("SELECT id FROM users WHERE phone = %s OR email = %s", (test_phone, f"{test_phone}@numer.app"))
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO users (email, password_hash, phone, name, birth_date, subscription) VALUES (%s, %s, %s, %s, %s, %s)",
                        (f"{test_phone}@numer.app", generate_password_hash(test_password), test_phone, 'Тест', '1990-01-01', 'Пламя')
                    )
                    print(f"[OK] Тестовый пользователь создан:")
                    print(f"   Телефон: +7 {test_phone[:3]} {test_phone[3:6]}-{test_phone[6:8]}-{test_phone[8:10]}")
                    print(f"   Пароль: {test_password}")
                conn.commit()
            else:
                existing = conn.execute(
                    "SELECT id FROM users WHERE phone = ? OR email = ?",
                    (test_phone, f"{test_phone}@numer.app")
                ).fetchone()
                
                if not existing:
                    conn.execute(
                        "INSERT INTO users (email, password_hash, phone, name, birth_date, subscription) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            f"{test_phone}@numer.app",
                            generate_password_hash(test_password),
                            test_phone,
                            'Тест',
                            '1990-01-01',
                            'Пламя'
                        )
                    )
                    print(f"[OK] Тестовый пользователь создан:")
                    print(f"   Телефон: +7 {test_phone[:3]} {test_phone[3:6]}-{test_phone[6:8]}-{test_phone[8:10]}")
                    print(f"   Пароль: {test_password}")
                conn.commit()


def cleanup_old_cache(max_age_days=30):
    try:
        days = int(max_age_days)
        with get_db() as conn:
            if USE_POSTGRES:
                cur = conn.cursor()
                cur.execute(
                    "DELETE FROM ai_cache WHERE created_at < NOW() - (%s * INTERVAL '1 day')",
                    (days,)
                )
            else:
                conn.execute(
                    "DELETE FROM ai_cache WHERE created_at < datetime('now', ?)",
                    (f'-{days} days',)
                )
            conn.commit()
    except Exception as e:
        print(f"Ошибка очистки кэша: {e}")


def cleanup_old_logs(max_age_days=90):
    try:
        days = int(max_age_days)
        with get_db() as conn:
            if USE_POSTGRES:
                cur = conn.cursor()
                cur.execute(
                    "DELETE FROM logs WHERE created_at < NOW() - (%s * INTERVAL '1 day')",
                    (days,)
                )
            else:
                conn.execute(
                    "DELETE FROM logs WHERE created_at < datetime('now', ?)",
                    (f'-{days} days',)
                )
            conn.commit()
    except Exception as e:
        print(f"Ошибка очистки логов: {e}")


def add_log(level, source, message):
    try:
        with get_db() as conn:
            if USE_POSTGRES:
                cur = conn.cursor()
                cur.execute("INSERT INTO logs (level, source, message) VALUES (%s, %s, %s)", (level, source, message))
            else:
                conn.execute("INSERT INTO logs (level, source, message) VALUES (?, ?, ?)", (level, source, message))
            conn.commit()
    except Exception as e:
        print(f"Ошибка записи лога: {e}")


if __name__ == '__main__':
    init_db()