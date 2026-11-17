import re
from datetime import datetime, date

# ===== НАСТРОЙКИ =====
# Список ID пользователей с расширенным тарифом (199₽/30д = 6.63₽/день)
EXTENDED_TARIFF_IDS = {
    1010897150, 1031689453, 1064951537, 1217913525, 1231128706, 1238187606,
    1303190643, 1362079732, 1707187797, 1732475183, 1971082454, 2018291980,
    2073470450, 211300420, 250579570, 331547417, 459855799, 5175764882,
    550438857, 5647217940, 630250854, 694501408, 7131344048, 7534497876,
    8120394120, 911454114, 942869596, 953082394
}

# Стоимость дня
BASIC_DAILY = 3.3      # 99₽/30д
EXTENDED_DAILY = 6.63  # 199₽/30д

# Дата, на которую считаем остаток (сегодня или фиксированная)
TODAY = date.today()  # или date(2026, 7, 1)

# Путь к файлу с логами (передаётся первым аргументом или вводится вручную)
import sys
if len(sys.argv) > 1:
    LOG_FILE = sys.argv[1]
else:
    LOG_FILE = input("Введите путь к файлу с логами /set_balance: ").strip()

# ===== ЧТЕНИЕ ЛОГОВ =====
pattern = re.compile(
    r'^/set_balance\s+(?P<uid>\d+)\s+(?P<amount>-?\d+(?:\.\d+)?)\s*[—–-]\s*(?P<date>\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2})'
)

latest = {}  # user_id -> (amount, datetime)

with open(LOG_FILE, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = pattern.search(line)
        if not m:
            continue
        uid = int(m.group('uid'))
        amount = float(m.group('amount'))
        dt_str = m.group('date')
        try:
            dt = datetime.strptime(dt_str, '%d.%m.%Y %H:%M:%S')
        except ValueError:
            continue  # пропускаем битые даты

        # Берём последнюю по дате запись для каждого пользователя
        if uid not in latest or dt > latest[uid][1]:
            latest[uid] = (amount, dt)

# ===== РАСЧЁТ ОСТАТКОВ =====
print("-- Восстановление балансов на", TODAY.strftime('%d.%m.%Y'))
print("-- Сгенерировано:", datetime.now().strftime('%d.%m.%Y %H:%M:%S'))
print()

total_remaining = 0.0
users_count = 0

for uid, (amount, dt) in sorted(latest.items()):
    daily = EXTENDED_DAILY if uid in EXTENDED_TARIFF_IDS else BASIC_DAILY
    days_passed = (TODAY - dt.date()).days
    remaining = amount - days_passed * daily
    if remaining < 0:
        remaining = 0.0

    # Округляем до двух знаков
    remaining = round(remaining, 2)
    total_remaining += remaining
    users_count += 1

    print(f"UPDATE users SET balance = {remaining:.2f} WHERE user_id = {uid};  -- пополнение {dt.strftime('%d.%m.%Y %H:%M')}, тариф {'расширенный' if daily > 4 else 'базовый'}, прошло {days_passed} дн.")

print()
print(f"-- Всего пользователей: {users_count}")
print(f"-- Общая сумма остатков: {total_remaining:.2f}₽")