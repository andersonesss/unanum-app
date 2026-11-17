# utils/stream_helpers.py
"""
Универсальные хелперы для SSE-стриминга (Server-Sent Events).

Контракт событий (фиксированный, не расширяется разделами):
    event: meta  — метаданные (section, знак, период, code, ...)
    event: chunk — кусочек текста (побуквенный стрим)
    event: block — готовый блок (name, value) для структур
    event: error — ошибка (message)
    event: done  — завершение (может содержать full_text, cached)

Этот модуль НЕ знает про разделы (чат, гороскоп, финкод, таро).
Разделы используют format_sse() и не придумывают новые типы событий —
это гарантирует независимость транспорта от логики.
"""

import json


ALLOWED_EVENTS = frozenset({'meta', 'chunk', 'block', 'error', 'done'})


def format_sse(event, data):
    """Собирает одно SSE-сообщение.

    event — строка из ALLOWED_EVENTS (meta, chunk, block, error, done).
    data  — любой JSON-сериализуемый объект (dict, list, str, ...).

    Возвращает строку формата SSE:
        event: chunk
        data: {"chunk": "..."}
    <пустая строка>
    """
    if event not in ALLOWED_EVENTS:
        raise ValueError(
            f"format_sse: неизвестный тип события '{event}'. "
            f"Разрешены только: {sorted(ALLOWED_EVENTS)}"
        )
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def stream_block_tasks(tasks, max_workers=6):
    """
    Параллельно запускает задачи, отдаёт результаты по мере готовности.

    Паттерн «очередь + воркеры»: ThreadPoolExecutor не позволяет делать
    yield из другого потока, поэтому воркеры кладут результаты в queue.Queue,
    а главный поток (генератор) читает из очереди и yield'ит.

    Параметры:
        tasks — список dict вида [{'name': str, 'fn': callable}, ...]
            name — имя блока (пойдёт в SSE-событие block как name)
            fn   — вызываемая без аргументов; должна вернуть
                   JSON-сериализуемый результат или None при ошибке
        max_workers — сколько потоков одновременно (по умолчанию 6)

    Возвращает генератор кортежей (name, result) в порядке готовности.
    Генератор завершается, когда все задачи отработали.

    Ошибки в отдельных задачах НЕ прерывают поток: если fn() бросил
    исключение, придёт (name, None) — раздел сам решит, что с этим делать.

    Пример:
        tasks = [
            {'name': 'love',   'fn': lambda: ai_horoscope_love('Овен', 'день')},
            {'name': 'career', 'fn': lambda: ai_horoscope_career('Овен', 'день')},
        ]
        for name, result in stream_block_tasks(tasks):
            if result is not None:
                yield format_sse('block', {'name': name, **result})
    """
    if not tasks:
        return

    import queue
    from concurrent.futures import ThreadPoolExecutor

    q = queue.Queue()

    def _run(task):
        """Обёртка вокруг задачи: перехватывает исключения и кладёт результат в очередь."""
        name = task.get('name')
        fn = task.get('fn')
        if not callable(fn):
            q.put((name, None))
            return
        try:
            result = fn()
            q.put((name, result))
        except Exception:
            # Тихая ошибка в задаче — раздел получит (name, None) и сам решит.
            # Логирование на этом уровне не делаем: если разделу важно —
            # пусть логирует у себя, зная контекст (какой блок, какой user_id).
            q.put((name, None))

    total = len(tasks)
    done_count = 0

    # with ThreadPoolExecutor блокирует выход, пока все задачи не доработают.
    # Это правильно: если клиент оборвал соединение (GeneratorExit при yield),
    # мы не оставим зомби-потоков. Максимальная задержка — время самой долгой
    # задачи (для гороскопа ~10-15 сек, для финкода ~15-20 сек).
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for task in tasks:
            executor.submit(_run, task)

        while done_count < total:
            name, result = q.get()
            done_count += 1
            yield name, result