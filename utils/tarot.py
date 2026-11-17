import os
import json
import logging
import random
from database.db import get_db, add_log

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    with open(os.path.join(_BASE_DIR, 'data', 'tarot_cards.json'), 'r', encoding='utf-8') as f:
        TAROT_DECK = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    logging.error(f"Не удалось загрузить колоду Таро: {e}")
    raise RuntimeError(
        "Файл data/tarot_cards.json не найден или повреждён. "
        "Положите колоду в data/tarot_cards.json."
    ) from e

MAJOR_ARCANA = [c for c in TAROT_DECK if c['arcana'] == 'major']

def get_card_image(card_id):
    return f"{card_id + 2:02d}.jpg"

def get_card_by_id(card_id):
    for card in TAROT_DECK:
        if card['id'] == card_id:
            return card
    return None

def draw_random_card(major_only=False):
    deck = MAJOR_ARCANA if major_only else TAROT_DECK
    card = random.choice(deck)
    is_reversed = random.choice([False, True])
    return card, is_reversed

def format_card_response(card, is_reversed=False):
    meaning = card['meaning_reversed'] if is_reversed else card['meaning_upright']
    position_text = " (перевёрнутая)" if is_reversed else ""

    return {
        "id": card['id'],
        "name": card['name_ru'] + position_text,
        "name_en": card['name_en'],
        "arcana": card['arcana'],
        "number": card['number'],
        "suit": card.get('suit', ''),
        "is_reversed": is_reversed,
        "meaning": meaning,
        "advice": card.get('advice', ''),
        "keywords": card.get('keywords', [])
    }

def get_daily_card(identifier=None, use_ai=True, user_email=None, user_subscription='Искра'):
    from utils.helpers import today_msk, now_msk
    today = today_msk()
    
    search_id = None
    if user_email:
        search_id = user_email
    elif identifier and str(identifier).strip():
        search_id = str(identifier).strip()
    
    # Вся работа в одной транзакции
    with get_db() as conn:
        if search_id:
            row = conn.execute(
                "SELECT * FROM daily_cards WHERE identifier = ? AND card_date = ?",
                (search_id, today)
            ).fetchone()
            if row:
                card = get_card_by_id(row['card_id'])
                if card:
                    result = format_card_response(card, bool(row['is_reversed']))
                    result['date'] = now_msk().strftime("%d.%m.%Y")
                    ai_text = row['ai_text'] if row['ai_text'] else None
                    if user_subscription == 'Искра' and ai_text:
                        if len(ai_text) > 55:
                            cutoff = max(int(len(ai_text) * 0.2), 50)
                            ai_text = ai_text[:cutoff] + '...'
                    result['ai_interpretation'] = ai_text
                    return result
        
        # Генерация новой карты
        card, is_reversed = draw_random_card()
        result = format_card_response(card, is_reversed)
        result['date'] = now_msk().strftime("%d.%m.%Y")
        
        ai_text = None
        if use_ai:
            ai_text = ai_daily_card(card, is_reversed, user_id=search_id)
        
        if user_subscription == 'Искра' and ai_text and len(ai_text) > 55:
            cutoff = max(int(len(ai_text) * 0.2), 50)
            ai_text = ai_text[:cutoff] + '...'
        result['ai_interpretation'] = ai_text
        
        if search_id:
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO daily_cards (identifier, card_date, card_id, is_reversed, ai_text) VALUES (?, ?, ?, ?, ?)",
                    (search_id, today, card['id'], int(is_reversed), ai_text or '')
                )
            except Exception as e:
                add_log('ERROR', 'tarot', f"Ошибка сохранения карты дня: {e}")
    
    add_log('INFO', 'tarot', f"Карта дня: {card['name_ru']} (reversed={is_reversed})")
    return result

def get_daily_card_stream(identifier=None, user_email=None, user_subscription='Искра'):
    """
    Генератор SSE-событий для карты дня.

    Отдаёт кортежи (event_type, event_data):
        ('meta',  {card-поля, date, cached})
        ('chunk', {'chunk': '...'})
        ('done',  {'full_text': '...', 'is_reversed': bool})
        ('error', {'message': '...'})

    Логика сохранения идентична get_daily_card:
    - карта дня определяется один раз на дату, сохраняется сразу с пустым ai_text;
    - после стрима сохраняется в БД: обрезанный текст для Искры (20%),
      полный — для Пламени;
    - при повторном запросе в тот же день отдаётся ai_text из БД.

    Старая get_daily_card не меняется — оба пути работают параллельно.
    """
    from utils.helpers import today_msk, now_msk
    from utils.ai_service import ask_deepseek_stream

    today = today_msk()

    search_id = None
    if user_email:
        search_id = user_email
    elif identifier and str(identifier).strip():
        search_id = str(identifier).strip()

    cached_ai_text = None
    card = None
    is_reversed = False

    # Фаза 1: пробуем достать карту дня из БД.
    if search_id:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM daily_cards WHERE identifier = ? AND card_date = ?",
                (search_id, today)
            ).fetchone()
            if row:
                card = get_card_by_id(row['card_id'])
                if card:
                    is_reversed = bool(row['is_reversed'])
                    cached_ai_text = row['ai_text'] or ''

    # Если карты нет — генерируем и сразу сохраняем (с пустым ai_text).
    # Если падение произойдёт дальше (DeepSeek недоступен), карта всё равно
    # уже зафиксирована на сегодня — пользователь получит ту же при повторе.
    if card is None:
        card, is_reversed = draw_random_card()
        if search_id:
            with get_db() as conn:
                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO daily_cards "
                        "(identifier, card_date, card_id, is_reversed, ai_text) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (search_id, today, card['id'], int(is_reversed), '')
                    )
                    conn.commit()
                except Exception as e:
                    add_log('ERROR', 'tarot', f"Ошибка сохранения карты дня: {e}")
        add_log('INFO', 'tarot', f"Карта дня: {card['name_ru']} (reversed={is_reversed})")

    # Фаза 2: meta — карта и её базовое описание (без AI-текста).
    meta = format_card_response(card, is_reversed)
    meta['date'] = now_msk().strftime("%d.%m.%Y")
    meta['cached'] = bool(cached_ai_text)
    yield ('meta', meta)

    # Фаза 3: если в БД уже есть ai_text — отдаём сразу, без DeepSeek.
    # Обрезка для Искры применяется та же, что была в get_daily_card.
    if cached_ai_text:
        ai_text = cached_ai_text
        if user_subscription == 'Искра' and len(ai_text) > 55:
            cutoff = max(int(len(ai_text) * 0.2), 50)
            ai_text = ai_text[:cutoff] + '...'
        yield ('chunk', {'chunk': ai_text})
        yield ('done', {'full_text': ai_text, 'is_reversed': is_reversed})
        return

    # Фаза 4: стрим к DeepSeek. Промпт — тот же, что в ai_daily_card.
    prompt = get_prompt_from_db('tarot_daily')
    if not prompt:
        yield ('error', {'message': 'Промпт карты дня не найден'})
        return

    position = "перевёрнутом" if is_reversed else "прямом"
    user_msg = (
        f"\n    Карта дня: {card['name_ru']} в {position} положении.\n"
        f"    Ключевые слова: {', '.join(card.get('keywords', []))}.\n"
        f"    Расскажи о значении этой карты на сегодня. Дай совет.\n    "
    )

    full_text = ""
    try:
        for chunk in ask_deepseek_stream(prompt, user_msg, temperature=0.7, user_id=search_id):
            if chunk is None:
                break
            full_text += chunk
            yield ('chunk', {'chunk': chunk})
    except Exception as e:
        add_log('ERROR', 'tarot', f"Ошибка стрима карты дня: {e}")
        yield ('error', {'message': 'Что-то пошло не так. Попробуйте ещё раз.'})
        return

    # Фаза 5: сохраняем результат в БД (обрезанный для Искры, полный — для Пламени).
    if search_id and full_text:
        saved_text = full_text
        if user_subscription == 'Искра' and len(full_text) > 55:
            cutoff = max(int(len(full_text) * 0.2), 50)
            saved_text = full_text[:cutoff] + '...'
        try:
            with get_db() as conn:
                conn.execute(
                    "UPDATE daily_cards SET ai_text = ? "
                    "WHERE identifier = ? AND card_date = ?",
                    (saved_text, search_id, today)
                )
                conn.commit()
        except Exception as e:
            add_log('ERROR', 'tarot', f"Ошибка сохранения текста карты дня: {e}")

    # Фаза 6: done. Отдаём полный текст — фронт сам решает, обрезать или нет.
    yield ('done', {'full_text': full_text, 'is_reversed': is_reversed})

def do_spread(spread_type='one_card', question='', identifier=None, use_ai=True):
    positions = []
    user_id = identifier if identifier else 'anonymous'

    if spread_type == 'one_card':
        labels = ["Карта-совет"]
    elif spread_type == 'three_card':
        labels = ["Прошлое", "Настоящее", "Будущее"]
    else:
        return {"error": "Неизвестный тип расклада"}

    used_ids = set()
    for label in labels:
        card, is_reversed = draw_random_card()
        while card['id'] in used_ids:
            card, is_reversed = draw_random_card()
        used_ids.add(card['id'])
        card_data = format_card_response(card, is_reversed)
        card_data['position'] = label
        positions.append(card_data)

    from utils.helpers import now_msk
    result = {
        "type": spread_type,
        "question": question,
        "cards": positions,
        "date": now_msk().strftime("%d.%m.%Y %H:%M")
    }

    if use_ai:
        result['ai_interpretation'] = ai_spread_interpretation(positions, question, user_id=user_id)

    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO spreads (user_id, spread_type, question, cards_data, ai_interpretation) VALUES (?, ?, ?, ?, ?)",
                (user_id, spread_type, question, json.dumps(positions, ensure_ascii=False),
                 result.get('ai_interpretation', ''))
            )
    except Exception as e:
        add_log('ERROR', 'tarot', f"Ошибка сохранения расклада: {e}")

    add_log('INFO', 'tarot', f"Расклад {spread_type}, вопрос: {question[:50]}")
    return result

def do_spread_stream(spread_type='one_card', question='', identifier=None, use_ai=True):
    """
    Генератор SSE-событий для расклада Таро.

    Отдаёт кортежи (event_type, event_data):
        ('meta',  {type, question, cards, date})
        ('chunk', {'chunk': '...'})            # только если use_ai=True
        ('done',  {'ai_interpretation': '...'})
        ('error', {'message': '...'})

    Логика выпадения карт — идентична do_spread (та же функция draw_random_card,
    тот же запрет повторов в раскладе). Сохранение в БД spreads — в конце,
    одной транзакцией, как в старой функции.

    Старая do_spread не меняется — оба пути работают параллельно.
    """
    from utils.helpers import now_msk
    from utils.ai_service import ask_deepseek_stream

    user_id = identifier if identifier else 'anonymous'

    if spread_type == 'one_card':
        labels = ["Карта-совет"]
    elif spread_type == 'three_card':
        labels = ["Прошлое", "Настоящее", "Будущее"]
    else:
        yield ('error', {'message': 'Неизвестный тип расклада'})
        return

    # Фаза 1: выпадают карты. Это мгновенно, без AI.
    positions = []
    used_ids = set()
    for label in labels:
        card, is_reversed = draw_random_card()
        while card['id'] in used_ids:
            card, is_reversed = draw_random_card()
        used_ids.add(card['id'])
        card_data = format_card_response(card, is_reversed)
        card_data['position'] = label
        positions.append(card_data)

    # Фаза 2: meta — карты и дата.
    yield ('meta', {
        'type': spread_type,
        'question': question,
        'cards': positions,
        'date': now_msk().strftime("%d.%m.%Y %H:%M"),
    })

    ai_interpretation = ''

    # Фаза 3: AI-толкование (только если use_ai=True).
    # Промпт и user_msg — дословно из ai_spread_interpretation.
    if use_ai:
        prompt = get_prompt_from_db('tarot_spread')
        if prompt:
            cards_text = ""
            for p in positions:
                pos_text = "перевёрнутая" if p['is_reversed'] else "прямая"
                cards_text += f"- {p['position']}: {p['name'].replace(' (перевёрнутая)', '')} ({pos_text})\n"

            user_msg = f"""
        Вопрос: {question if question else 'Общий расклад'}
        Карты:
        {cards_text}
        
        Если вопрос задан — синтезируй значение расклада строго в контексте этого вопроса. 
        Свяжи каждую карту с вопросом. Дай совет, отвечающий на вопрос.
        Если вопрос не задан — дай общее толкование.
        """

            try:
                for chunk in ask_deepseek_stream(prompt, user_msg, user_id=user_id):
                    if chunk is None:
                        break
                    ai_interpretation += chunk
                    yield ('chunk', {'chunk': chunk})
            except Exception as e:
                add_log('ERROR', 'tarot', f"Ошибка стрима расклада: {e}")
                yield ('error', {'message': 'Что-то пошло не так. Попробуйте ещё раз.'})
                return

    # Фаза 4: сохранение в БД — один INSERT, как в do_spread.
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO spreads (user_id, spread_type, question, cards_data, ai_interpretation) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, spread_type, question, json.dumps(positions, ensure_ascii=False), ai_interpretation)
            )
    except Exception as e:
        add_log('ERROR', 'tarot', f"Ошибка сохранения расклада: {e}")

    add_log('INFO', 'tarot', f"Расклад {spread_type}, вопрос: {question[:50]}")

    # Фаза 5: завершение.
    yield ('done', {'ai_interpretation': ai_interpretation})

def search_cards(query='', arcana_filter='all', suit_filter='all', sort_by='number'):
    results = []
    query = query.lower().strip()

    for card in TAROT_DECK:
        if arcana_filter == 'major' and card['arcana'] != 'major':
            continue
        if arcana_filter == 'minor' and card['arcana'] != 'minor':
            continue
        if suit_filter != 'all' and card.get('suit', '') != suit_filter:
            continue
        if query:
            name_match = query in card['name_ru'].lower() or query in card['name_en'].lower()
            keyword_match = any(query in kw.lower() for kw in card.get('keywords', []))
            if not name_match and not keyword_match:
                continue

        results.append({
            "id": card['id'],
            "name_ru": card['name_ru'],
            "name_en": card['name_en'],
            "arcana": card['arcana'],
            "number": card['number'],
            "suit": card.get('suit', ''),
            "keywords": card.get('keywords', [])
        })

    suit_order = {'wands': 0, 'cups': 1, 'swords': 2, 'pentacles': 3}

    if sort_by == 'name':
        results.sort(key=lambda c: c['name_ru'])
    elif sort_by == 'suit':
        results.sort(key=lambda c: (c['arcana'], suit_order.get(c['suit'], 99), c['id']))
    else:
        results.sort(key=lambda c: c['id'])

    return {
        "total": len(results),
        "cards": results
    }

def get_card_detail(card_id):
    card = get_card_by_id(card_id)
    if not card:
        return {"error": "Карта не найдена"}

    return {
        "id": card['id'],
        "name_ru": card['name_ru'],
        "name_en": card['name_en'],
        "arcana": card['arcana'],
        "number": card['number'],
        "suit": card.get('suit', ''),
        "keywords": card.get('keywords', []),
        "meaning_upright": card['meaning_upright'],
        "meaning_reversed": card['meaning_reversed'],
        "advice": card.get('advice', '')
    }

def ai_daily_card(card, is_reversed, user_id=None):
    from utils.ai_service import ask_deepseek

    prompt = get_prompt_from_db('tarot_daily')
    if not prompt:
        return None

    position = "перевёрнутом" if is_reversed else "прямом"
    user_msg = f"""
    Карта дня: {card['name_ru']} в {position} положении.
    Ключевые слова: {', '.join(card.get('keywords', []))}.
    Расскажи о значении этой карты на сегодня. Дай совет.
    """
    return ask_deepseek(prompt, user_msg, temperature=0.7, user_id=user_id)

def ai_spread_interpretation(positions, question='', user_id=None):
    from utils.ai_service import ask_deepseek

    prompt = get_prompt_from_db('tarot_spread')
    if not prompt:
        return None

    cards_text = ""
    for p in positions:
        pos_text = "перевёрнутая" if p['is_reversed'] else "прямая"
        cards_text += f"- {p['position']}: {p['name'].replace(' (перевёрнутая)', '')} ({pos_text})\n"

    user_msg = f"""
        Вопрос: {question if question else 'Общий расклад'}
        Карты:
        {cards_text}
        
        Если вопрос задан — синтезируй значение расклада строго в контексте этого вопроса. 
        Свяжи каждую карту с вопросом. Дай совет, отвечающий на вопрос.
        Если вопрос не задан — дай общее толкование.
        """
    return ask_deepseek(prompt, user_msg, user_id=user_id)

def get_prompt_from_db(prompt_name):
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT content FROM prompts WHERE name = ?", (prompt_name,))
            row = c.fetchone()
            if row:
                return row['content']
    except Exception as e:
        add_log('ERROR', 'tarot', f"Ошибка получения промпта {prompt_name}: {e}")

    try:
        with open(os.path.join(_BASE_DIR, 'data', 'default_prompts.json'), 'r', encoding='utf-8') as f:
            prompts = json.load(f)
            for p in prompts:
                if p['name'] == prompt_name:
                    return p['content']
    except:
        pass
    return None

if __name__ == '__main__':
    print("=== КАРТА ДНЯ ===")
    daily = get_daily_card(use_ai=False)
    print(json.dumps(daily, ensure_ascii=False, indent=2))

    print("\n=== РАСКЛАД ТРИ КАРТЫ ===")
    spread = do_spread('three_card', 'Что меня ждёт в любви?', use_ai=False)
    print(json.dumps(spread, ensure_ascii=False, indent=2))

    print("\n=== ПОИСК ===")
    result = search_cards('любовь')
    print(f"Найдено: {result['total']} карт")