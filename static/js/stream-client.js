// ============================================
// stream-client.js — универсальный SSE-клиент unanum
// ============================================
//
// Один раз для всего проекта. Не знает про разделы
// (чат, гороскоп, финкод, таро...). Задача — открыть
// SSE-поток, распарсить события и вызвать колбэки.
//
// Контракт событий (совпадает с utils/stream_helpers.py):
//     event: meta  → onMeta({section, ...})
//     event: chunk → onChunk({chunk, [name], [phase], ...})
//                     chunk — кусок текста (обязательное поле)
//                     name  — имя блока-получателя (опционально; для
//                             мультиблочного стрима, например 'digit_0')
//                     phase — фаза блока ('teaser'|'full'|'main'|'premium')
//     event: block → onBlock({name, value, ...})
//     event: error → onError({message})
//     event: done  → onDone({full_text, cached})
//
// Использование:
//     streamPost('/api/horoscope/stream', {zodiac_sign: 'aries'}, {
//         onMeta:  (meta) => console.log('meta', meta),
//         onChunk: (text) => appendToDOM(text),
//         onDone:  (data) => console.log('done', data),
//         onError: (err)  => showError(err.message),
//     });
//
// Функция возвращает Promise, который resolve'ится при завершении
// потока (после onDone или onError) — удобно для await / .then().

async function streamPost(url, payload, handlers = {}) {
    const {
        onMeta,
        onChunk,
        onBlock,
        onError,
        onDone,
    } = handlers;

    // ---- 1. Открываем запрос ----
    let response;
    try {
        // window.fetch обёрнут в main.js — CSRF-заголовок добавится сам.
        response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload || {}),
        });
    } catch (e) {
        // Сетевая ошибка (сервер недоступен, DNS, CORS).
        if (onError) onError({ message: 'Ошибка соединения. Проверьте интернет.' });
        return;
    }

    // ---- 2. HTTP-ошибка до старта стрима ----
    // Сервер может вернуть JSON с ошибкой (например, 402 при лимите вопросов).
    // Это ещё не SSE — читаем как JSON и отдаём в onError.
    if (!response.ok) {
        let errData = { message: `Ошибка ${response.status}` };
        try {
            const json = await response.json();
            if (json && (json.message || json.error)) {
                errData.message = json.message || json.error;
            }
        } catch (_) {
            // Тело не JSON — оставляем дефолтное сообщение.
        }
        if (onError) onError(errData);
        return;
    }

    // ---- 3. Проверка поддержки стриминга ----
    if (!response.body || typeof response.body.getReader !== 'function') {
        if (onError) onError({ message: 'Браузер не поддерживает стриминг ответов.' });
        return;
    }

    // ---- 4. Чтение потока ----
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    try {
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            // stream: true — не рвать многобайтовые UTF-8 символы на границе чанков.
            buffer += decoder.decode(value, { stream: true });

            // Разделитель SSE-событий — двойной перевод строки.
            let idx;
            while ((idx = buffer.indexOf('\n\n')) !== -1) {
                const rawEvent = buffer.slice(0, idx);
                buffer = buffer.slice(idx + 2);

                // Разбираем одну SSE-запись: строки event: и data:.
                let eventType = 'message';
                let dataStr = '';
                for (const line of rawEvent.split('\n')) {
                    if (line.startsWith('event:')) {
                        eventType = line.slice(6).trim();
                    } else if (line.startsWith('data:')) {
                        // data может быть в несколько строк — склеиваем.
                        dataStr += line.slice(5).trim();
                    }
                }
                if (!dataStr) continue;

                // Парсим JSON.
                let data;
                try {
                    data = JSON.parse(dataStr);
                } catch (e) {
                    console.warn('[streamPost] bad JSON in SSE:', dataStr);
                    continue;
                }

                // Диспетчеризация по типу события.
                // try/catch вокруг каждого колбэка: ошибка в разделе не должна
                // рвать обработку остальных событий.
                try {
                    if (eventType === 'meta') {
                        if (onMeta) onMeta(data);
                    } else if (eventType === 'chunk') {
                        // Передаём полный объект: {chunk: '...', name?: '...', phase?: '...'}.
                        // Чат использует data.chunk, финкод дополнительно читает data.name.
                        if (onChunk) onChunk(data);
                    } else if (eventType === 'block') {
                        if (onBlock) onBlock(data);
                    } else if (eventType === 'error') {
                        if (onError) onError(data);
                        return; // сервер сказал — поток больше не продолжаем
                    } else if (eventType === 'done') {
                        if (onDone) onDone(data);
                        return; // нормальное завершение
                    }
                    // Неизвестный eventType игнорируем молча — это защита
                    // от будущих расширений контракта без изменения клиента.
                } catch (e) {
                    console.error('[streamPost] handler error:', e);
                }
            }
        }

        // Поток закончился, не прислав явный event: done.
        // Например, клиент отменил запрос или сервер упал молча.
        // Считаем завершённым без ошибки — вызывающий сам решит, что делать.
    } catch (e) {
        // Ошибка чтения потока (например, соединение оборвалось).
        if (onError) onError({ message: 'Соединение прервано.' });
    } finally {
        // Освобождаем reader (важно для Safari / Firefox).
        try { reader.releaseLock(); } catch (_) {}
    }
}