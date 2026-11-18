// ============================================
// unanum - Main JavaScript
// ============================================

function getDeviceFingerprint() {
    let fp = localStorage.getItem('deviceFp');
    if (!fp) {
        fp = 'fp_' + Math.random().toString(36).substr(2, 10) + Date.now().toString(36);
        localStorage.setItem('deviceFp', fp);
    }
    return fp;
}

function sanitizeHTML(str) {
    if (!str || typeof str !== 'string') return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Алиас для совместимости: escapeHTML используется в inline-скриптах base.html и natal_chart.html
const escapeHTML = sanitizeHTML;

const zodiacSvgs = {
    'aries': '<svg width="18" height="18" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg"><g id="Layer_2"><g id="invisible_box"><rect width="48" height="48" fill="none"/></g><g id="horoscope"><path d="M41.1,5.7a8,8,0,0,0-8.8,1.6L24,15.2,15.7,7.3A8,8,0,0,0,6.9,5.7,7.9,7.9,0,0,0,2,13a8,8,0,0,0,8.1,8h.2a2,2,0,0,0,0-4h-.2A4,4,0,0,1,6,13,4,4,0,0,1,8.5,9.3a4.2,4.2,0,0,1,4.5.9l9,8.6V41a2,2,0,0,0,4,0V18.8l9-8.6a4.2,4.2,0,0,1,4.5-.9A4,4,0,0,1,42,13a4,4,0,0,1-4.1,4h-.2a2,2,0,0,0,0,4h.2A8,8,0,0,0,46,13,7.9,7.9,0,0,0,41.1,5.7Z" fill="currentColor"/></g></g></svg>',
    'taurus': '<svg width="18" height="18" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg"><g id="Layer_2"><g id="invisible_box"><rect width="48" height="48" fill="none"/></g><g id="Horoscope"><path d="M42,3h-.5a8.1,8.1,0,0,0-5.9,2.6l-8,11.9A14.2,14.2,0,0,0,24,17a14.2,14.2,0,0,0-3.6.5L12.6,5.9l-.2-.3A8.1,8.1,0,0,0,6.5,3H6A2,2,0,0,0,6,7h.5A4,4,0,0,1,9.4,8.2l7.3,10.9a14,14,0,1,0,14.6,0L38.6,8.2A4,4,0,0,1,41.5,7H42a2,2,0,0,0,0-4ZM34,31A10,10,0,1,1,24,21,10,10,0,0,1,34,31Z" fill="currentColor"/></g></g></svg>',
    'gemini': '<svg width="18" height="18" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg"><g id="Layer_2"><g id="invisible_box"><rect width="48" height="48" fill="none"/></g><g id="Horoscope"><path d="M33,34.1V11.9A26.5,26.5,0,0,0,43.4,5.4a1.9,1.9,0,0,0,0-2.8,1.9,1.9,0,0,0-2.8,0,23.6,23.6,0,0,1-33.2,0,1.9,1.9,0,0,0-2.8,0,1.9,1.9,0,0,0,0,2.8A26.5,26.5,0,0,0,15,11.9V34.1A26.5,26.5,0,0,0,4.6,40.6a1.9,1.9,0,0,0,0,2.8,1.9,1.9,0,0,0,2.8,0,23.6,23.6,0,0,1,33.2,0,1.9,1.9,0,0,0,2.8,0,1.9,1.9,0,0,0,0-2.8A26.5,26.5,0,0,0,33,34.1ZM19,33V13a27.3,27.3,0,0,0,5,.5,27.3,27.3,0,0,0,5-.5V33a27.3,27.3,0,0,0-5-.5A27.3,27.3,0,0,0,19,33Z" fill="currentColor"/></g></g></svg>',
    'cancer': '<svg width="18" height="18" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg"><g id="Layer_2"><g id="invisible_box"><rect width="48" height="48" fill="none"/></g><g id="Horoscope"><g><path d="M11.9,30H12a9.9,9.9,0,0,0,4.6-18.7l-1.5-.6c9.5-4.8,19.5-3.2,27.5,4.8a2,2,0,1,0,2.8-2.8C34,1.1,18.2,1.1,5.3,12.6a9.9,9.9,0,0,0-2.6,11A9.6,9.6,0,0,0,11.9,30ZM12,14a6,6,0,1,1-6,6A6,6,0,0,1,12,14Z" fill="currentColor"/><path d="M36.1,18H36a9.9,9.9,0,0,0-4.6,18.7,9.4,9.4,0,0,0,1.5.6c-9.5,4.8-19.5,3.2-27.5-4.8a1.9,1.9,0,0,0-2.8,0,1.9,1.9,0,0,0,0,2.8c11.4,11.6,27.2,11.6,40.1.1a9.9,9.9,0,0,0,2.6-11A9.6,9.6,0,0,0,36.1,18ZM36,34a6,6,0,1,1,6-6A6,6,0,0,1,36,34Z" fill="currentColor"/></g></g></svg>',
    'leo': '<svg width="18" height="18" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg"><g id="Layer_2"><g id="invisible_box"><rect width="48" height="48" fill="none"/></g><g id="Horoscope"><path d="M43,40H39.6a7.8,7.8,0,0,1-6.9-3.9,8,8,0,0,1-.2-7.8l4.6-8.7a12.1,12.1,0,0,0-.4-11.8A12,12,0,0,0,26.4,2H23.6A12,12,0,0,0,13.3,7.8a12.1,12.1,0,0,0-.4,11.8l1.8,3.6L13,23A10,10,0,1,0,23,33a9.8,9.8,0,0,0-1.4-5.1L16.5,17.7a8,8,0,0,1,.2-7.8A7.8,7.8,0,0,1,23.6,6h2.8a7.8,7.8,0,0,1,6.9,3.9,8,8,0,0,1,.2,7.8l-4.6,8.7a12.1,12.1,0,0,0,.4,11.8A12,12,0,0,0,39.6,44H43a2,2,0,0,0,0-4ZM13,39a6,6,0,0,1,0-12,5.8,5.8,0,0,1,5,2.8l.6,1.1h0A5.2,5.2,0,0,1,19,33,6,6,0,0,1,13,39Z" fill="currentColor"/></g></g></svg>',
    'virgo': '<svg width="18" height="18" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg"><g id="Layer_2"><g id="invisible_box"><rect width="48" height="48" fill="none"/></g><g id="Horoscope"><path d="M45.7,39.9,37.1,26l5.3-8.3A9.4,9.4,0,0,0,43.1,8a9.3,9.3,0,0,0-8.3-5,9.6,9.6,0,0,0-6.1,2.3A6,6,0,0,0,24,3a6.4,6.4,0,0,0-4,1.5A6.4,6.4,0,0,0,16,3a6.4,6.4,0,0,0-4,1.5A6.4,6.4,0,0,0,8,3,6,6,0,0,0,2,9v6a2,2,0,0,0,4,0V9a2,2,0,0,1,4,0V34a2,2,0,0,0,4,0V9a2,2,0,0,1,4,0V34a2,2,0,0,0,4,0V9a2,2,0,0,1,4,0v.4a9.3,9.3,0,0,0,1.1,8.1l5.2,8.4-9,14a2,2,0,0,0,3.4,2.2l8-12.4,7.6,12.4A2,2,0,0,0,44,43a2.3,2.3,0,0,0,1.1-.3A2.1,2.1,0,0,0,45.7,39.9ZM30.5,15.3a5,5,0,0,1-.3-5.5,5.2,5.2,0,0,1,9.3.1,5,5,0,0,1-.4,5.5l-4.4,6.8Z" fill="currentColor"/></g></g></svg>',
    'libra': '<svg width="18" height="18" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg"><g id="Layer_2"><g id="invisible_box"><rect width="48" height="48" fill="none"/></g><g id="Horoscope"><g><path d="M4,35H16.2a2.1,2.1,0,0,0,2-1.5,2.2,2.2,0,0,0-.9-2.2A12.9,12.9,0,0,1,11,20.1a13,13,0,1,1,26,0,12.9,12.9,0,0,1-6.3,11.2,2.2,2.2,0,0,0-.9,2.2,2.1,2.1,0,0,0,2,1.5H44a2,2,0,0,0,0-4H37.1a17,17,0,1,0-26.2,0H4a2,2,0,0,0,0,4Z" fill="currentColor"/><path d="M44,39H4a2,2,0,0,0,0,4H44a2,2,0,0,0,0-4Z" fill="currentColor"/></g></g></svg>',
    'scorpio': '<svg width="18" height="18" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg"><g id="Layer_2"><g id="invisible_box"><rect width="48" height="48" fill="none"/></g><g id="Horoscope"><path d="M45.4,37.6l-4-4a2,2,0,0,0-2.8,2.8l.6.6H38a2,2,0,0,1-2-2V10A7,7,0,0,0,24,5.1a7,7,0,0,0-10,0A7,7,0,0,0,2,10v5a2,2,0,0,0,4,0V10A2.9,2.9,0,0,1,9,7a2.9,2.9,0,0,1,3,3V34a2,2,0,0,0,4,0V10a3,3,0,0,1,6,0V34a2,2,0,0,0,4,0V10a3,3,0,0,1,6,0V35a6,6,0,0,0,6,6h1.2l-.6.6a1.9,1.9,0,0,0,0,2.8,1.9,1.9,0,0,0,2.8,0l4-4A1.9,1.9,0,0,0,45.4,37.6Z" fill="currentColor"/></g></g></svg>',
    'sagittarius': '<svg width="18" height="18" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg"><g id="Layer_2"><g id="invisible_box"><rect width="48" height="48" fill="none"/></g><g id="Horoscope"><path d="M41,5H21a2,2,0,0,0,0,4H36.2L18,27.2l-5.6-5.6a2,2,0,0,0-2.8,2.8L15.2,30,5.6,39.6a1.9,1.9,0,0,0,0,2.8,1.9,1.9,0,0,0,2.8,0L18,32.8l5.6,5.6a1.9,1.9,0,0,0,2.8,0,1.9,1.9,0,0,0,0-2.8L20.8,30,39,11.8V27a2,2,0,0,0,4,0V7A2,2,0,0,0,41,5Z" fill="currentColor"/></g></g></svg>',
    'capricorn': '<svg width="18" height="18" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg"><g id="Layer_2"><g id="invisible_box"><rect width="48" height="48" fill="none"/></g><g id="Horoscope"><path d="M36,24a9.5,9.5,0,0,0-5,1.5V11a8,8,0,0,0-8-8,8.2,8.2,0,0,0-6,2.7A8.2,8.2,0,0,0,11,3a8,8,0,0,0-8,8v4a2,2,0,0,0,4,0V11a4,4,0,0,1,8,0V34a2,2,0,0,0,4,0V11a4,4,0,0,1,8,0V37a4,4,0,0,1-4,4H21a2,2,0,0,0,0,4h2a8.1,8.1,0,0,0,7.4-5A8.5,8.5,0,0,0,36,42a9,9,0,0,0,0-18Zm0,14a5,5,0,1,1,5-5A5,5,0,0,1,36,38Z" fill="currentColor"/></g></g></svg>',
    'aquarius': '<svg width="18" height="18" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg"><g id="Layer_2"><g id="invisible_box"><rect width="48" height="48" fill="none"/></g><g id="Horoscope"><g><path d="M42,27a2,2,0,0,0-2,2v2a4,4,0,0,1-8,0V29a2,2,0,0,0-4,0v2a4,4,0,0,1-8,0V29a2,2,0,0,0-4,0v2a4,4,0,0,1-8,0V29a2,2,0,0,0-4,0v2a8,8,0,0,0,8,8,8.2,8.2,0,0,0,6-2.7,8,8,0,0,0,12,0A8.2,8.2,0,0,0,36,39a8,8,0,0,0,8-8V29A2,2,0,0,0,42,27Z" fill="currentColor"/><path d="M42,9a2,2,0,0,0-2,2v2a4,4,0,0,1-8,0V11a2,2,0,0,0-4,0v2a4,4,0,0,1-8,0V11a2,2,0,0,0-4,0v2a4,4,0,0,1-8,0V11a2,2,0,0,0-4,0v2a8,8,0,0,0,8,8,8.2,8.2,0,0,0,6-2.7,8,8,0,0,0,12,0A8.2,8.2,0,0,0,36,21a8,8,0,0,0,8-8V11A2,2,0,0,0,42,9Z" fill="currentColor"/></g></g></svg>',
    'pisces': '<svg width="18" height="18" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg"><g id="Layer_2"><g id="invisible_box"><rect width="48" height="48" fill="none"/></g><g id="Horoscope"><path d="M43,22H33.7A23,23,0,0,1,40.4,7.4a1.9,1.9,0,0,0,0-2.8,1.9,1.9,0,0,0-2.8,0,27.3,27.3,0,0,0-8,17.4H18.4a27.3,27.3,0,0,0-8-17.4,1.9,1.9,0,0,0-2.8,0,1.9,1.9,0,0,0,0,2.8A23,23,0,0,1,14.3,22H5a2,2,0,0,0,0,4h9.3A23,23,0,0,1,7.6,40.6a1.9,1.9,0,0,0,0,2.8,1.9,1.9,0,0,0,2.8,0,27.3,27.3,0,0,0,8-17.4H29.6a27.3,27.3,0,0,0,8,17.4,1.9,1.9,0,0,0,2.8,0,1.9,1.9,0,0,0,0-2.8A23,23,0,0,1,33.7,26H43a2,2,0,0,0,0-4Z" fill="currentColor"/></g></g></svg>'
};

const origFetch = window.fetch;
window.fetch = function(url, options = {}) {
    // Кастомные заголовки добавляем ТОЛЬКО для same-origin запросов.
    // Для cross-origin (например, Nominatim, ipapi.co) это вызвало бы CORS preflight
    // с заголовками, которые сторонний API может не разрешить.
    const urlStr = (typeof url === 'string') ? url : (url && url.url) || '';
    const isSameOrigin = urlStr.startsWith('/') || urlStr.startsWith(window.location.origin);

    if (isSameOrigin) {
        options.headers = options.headers || {};
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        if (csrfMeta) {
            options.headers['X-CSRFToken'] = csrfMeta.getAttribute('content');
        }
        options.headers['X-Device-Fingerprint'] = getDeviceFingerprint();
    }
    return origFetch.call(this, url, options);
};

// ========== ИНИЦИАЛИЗАЦИЯ ПРИ ЗАГРУЗКЕ ==========
document.addEventListener('DOMContentLoaded', () => {
    createStars();
    initModal();
    initTabBar();
    initDailyCardModal();
    if (document.getElementById('cardsGrid')) {
        loadLibraryCards();
    }
    if (document.getElementById('dailyHistory')) {
        loadDailyHistory();
    }
    checkTariffUpgrade();

    // Ежедневный опрос настроения. Задержка 3с — после онбординга (checkInit, 2с),
    // чтобы модалки не накладывались друг на друга. checkDailyInsight сам
    // выходит, если сегодня уже отвечено или если открыт /moon-calendar.
    // ОТКЛЮЧЕНО (2026-11-18): окно "Какой ты сегодня цветок? / Вопрос 1 из 3"
    // временно не показываем. Вернуть — раскомментировать строку ниже.
    // setTimeout(checkDailyInsight, 3000);

    // Приветственный экран + ротация hero-текстов
    (function() {
        const badge = document.getElementById('welcomeBadge');
        const titleEl = document.querySelector('.hero-title');
        const subtitleEl = document.querySelector('.hero-subtitle');
        
        if (!badge || !titleEl || !subtitleEl) return;
        
        const texts = [
            {
                title: 'Твоя вселенная говорит —<br>научись её слышать',
                subtitle: 'Числа, карты и луна раскроют то,<br>что ты всегда знал внутри.'
            },
            {
                title: 'Звёзды уже знают ответ.<br>Осталось только спросить.',
                subtitle: 'Гороскоп, Таро и нумерология<br>в одном пространстве.'
            },
            {
                title: 'Ты — больше, чем просто имя<br>и дата рождения.',
                subtitle: 'Раскрой свой финансовый код,<br>узнай карту дня и лунный ритм.'
            },
            {
                title: 'Числа не врут, карты не<br>случайны, луна не молчит.',
                subtitle: 'Твой персональный компас<br>в мире нумерологии и Таро.'
            },
            {
                title: 'Ты ищешь ответы —<br>они уже внутри тебя.',
                subtitle: 'Мы просто поможем их увидеть<br>через числа, звёзды и карты.'
            },
            {
                title: 'Каждое утро луна шепчет<br>тебе новый совет.',
                subtitle: 'А карта дня и финансовый код<br>раскрывают то, что скрыто.'
            },
            {
                title: 'Судьба пишется числами,<br>а характер — картами.',
                subtitle: 'Твой личный гороскоп, расклад<br>и нумерологический портрет.'
            },
            {
                title: 'Целая вселенная говорит<br>с тобой каждый день.',
                subtitle: 'Луна, Таро и числа<br>помогают понять её послания.'
            },
            {
                title: 'Жизнь — не хаос, а узор<br>из чисел, карт и лунных фаз.',
                subtitle: 'Узнай свой код, расклад<br>и гороскоп на сегодня.'
            },
            {
                title: 'Что если бы ты мог<br>заглянуть за занавес?',
                subtitle: 'Карта дня, совет луны<br>и твоё число судьбы уже здесь.'
            }
        ];
        
        // Выбираем случайный текст
        let usedIndexes = JSON.parse(sessionStorage.getItem('seenHeroTexts') || '[]');
        let availableIndexes = texts.map((_, i) => i).filter(i => !usedIndexes.includes(i));
        
        if (availableIndexes.length === 0) {
            usedIndexes = [];
            availableIndexes = texts.map((_, i) => i);
        }
        
        const randomIndex = availableIndexes[Math.floor(Math.random() * availableIndexes.length)];
        usedIndexes.push(randomIndex);
        sessionStorage.setItem('seenHeroTexts', JSON.stringify(usedIndexes));
        
        const chosen = texts[randomIndex];

        // Подставляем заголовок с градиентным highlight
        const titleParts = chosen.title.split('<br>');
        if (titleParts.length === 2) {
            titleEl.innerHTML = titleParts[0] + '<br><span class="hero-highlight">' + titleParts[1] + '</span>';
        } else {
            titleEl.innerHTML = chosen.title;
        }
        
        // Подзаголовок — с поддержкой <br>
        subtitleEl.innerHTML = chosen.subtitle;

        // Показываем бейдж только при первом визите
        if (document.cookie.indexOf('visited_before=') === -1) {
            badge.style.display = 'inline-block';
            const expires = new Date();
            expires.setFullYear(expires.getFullYear() + 1);
            document.cookie = 'visited_before=1; path=/; expires=' + expires.toUTCString();
        } else {
            badge.style.display = 'none';
        }
    })();

    // Установка знака зодиака в хедере
    (function() {
        const zodiacEl = document.getElementById('userZodiac');
        if (!zodiacEl) return;

        if (window.isAuthenticated && window.isAuthenticated !== 'false') {
            fetch('/api/profile/data')
                .then(r => r.json())
                .then(profile => {
                    if (profile.birth_date) {
                        const zodiacKey = getZodiacKey(profile.birth_date);
                        if (zodiacKey && zodiacSvgs[zodiacKey]) {
                            zodiacEl.innerHTML = zodiacSvgs[zodiacKey];
                            zodiacEl.style.display = 'inline-flex';
                        }
                    }
                });
        }
    })();
});

function openMenuModal() {
    document.getElementById('sideMenu').classList.add('open');
    document.getElementById('menuOverlay').classList.add('active');
}
function closeMenuModal() {
    document.getElementById('sideMenu').classList.remove('open');
    document.getElementById('menuOverlay').classList.remove('active');
}
function clearSelection() {
    if (window.getSelection) {
        window.getSelection().removeAllRanges();
    }
}



// ============================================
// ЗВЁЗДЫ
// ============================================

function createStars() {
    const container = document.getElementById('starsContainer');
    if (!container) return;
    for (let i = 0; i < 120; i++) {
        const star = document.createElement('div');
        star.classList.add('star');
        const size = Math.random() * 3 + 1;
        star.style.cssText = `
            width:${size}px; height:${size}px;
            left:${Math.random()*100}%; top:${Math.random()*100}%;
            --duration:${Math.random()*4+3}s;
            --delay:${Math.random()*5}s;
            background: #ffd54f;
            box-shadow: 0 0 ${size*3}px rgba(255, 213, 79, 0.6);
        `;
        container.appendChild(star);
    }
}

// ============================================
// ИСТОРИЯ КАРТ ДНЯ
// ============================================

async function loadDailyHistory() {
    const container = document.getElementById('dailyHistory');
    if (!container) return;
    
    try {
        const res = await fetch('/api/tarot/daily/history');
        const history = await res.json();
        
        if (history.length === 0) {
            container.innerHTML = '<p style="color:var(--color-text-lighter);">Пока нет истории.</p>';
            return;
        }
        
        let html = '';
        history.forEach(h => {
            const imgFile = `${String(h.card_id + 2).padStart(2, '0')}.jpg`;
            html += `
                <div style="min-width:100px;text-align:center;background:rgba(30,58,30,0.6);border:1px solid var(--color-border);border-radius:12px;padding:10px;cursor:pointer;" onclick="openCardDetail(${h.card_id})">
                    <img src="/static/images/tarot/${imgFile}" alt="${sanitizeHTML(h.name_ru)}" loading="lazy" style="width:80px;height:120px;object-fit:cover;border-radius:8px;${h.is_reversed ? 'transform:rotate(180deg);' : ''}">
                    <p style="font-size:11px;color:var(--color-text-light);margin-top:6px;">${sanitizeHTML(h.name_ru)}</p>
                    <p style="font-size:10px;color:var(--color-text-lighter);">${sanitizeHTML(h.date)}</p>
                </div>`;
        });
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<p style="color:var(--color-text-lighter);">Не удалось загрузить историю.</p>';
    }
}

// ============================================
// МОДАЛКИ
// ============================================

function openAuthModal() { document.getElementById('authModal').classList.add('active'); }
function closeAuthModal() { document.getElementById('authModal').classList.remove('active'); }

function initModal() {
    const authOverlay = document.getElementById('authModal');
    if (authOverlay) {
        authOverlay.addEventListener('click', e => { if (e.target === authOverlay) closeAuthModal(); });
    }

    // registerModal: обработчик был в inline-скрипте base.html.
    // Теперь единственный initModal — здесь, поэтому переносим сюда,
    // иначе закрытие регистрации по клику на оверлей перестанет работать.
    const registerOverlay = document.getElementById('registerModal');
    if (registerOverlay) {
        registerOverlay.addEventListener('click', e => { if (e.target === registerOverlay) closeRegisterModal(); });
    }

    const paywallOverlay = document.getElementById('paywallModal');
    if (paywallOverlay) {
        paywallOverlay.addEventListener('click', e => { if (e.target === paywallOverlay) closePaywall(); });
    }

    const insightOverlay = document.getElementById('insightModal');
    if (insightOverlay) {
        insightOverlay.addEventListener('click', e => { if (e.target === insightOverlay) closeInsightModal(true); });
    }

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            closeAuthModal();
            closeRegisterModal();
            closeDailyCardModal();
            closePaywall();
            clearSelection();
        }
    });
}

async function logoutUser() {
    try {
        const res = await fetch('/logout', { method: 'POST' });
        const data = await res.json();
        window.location.href = (data && data.redirect) || '/';
    } catch (e) {
        window.location.href = '/';
    }
}

// ============================================
// НОВАЯ РЕГИСТРАЦИЯ ЧЕРЕЗ ЗВОНОК
// ============================================

function openRegisterModal() {
    document.getElementById('registerModal').classList.add('active');
    // Сбрасываем на шаг 1
    document.getElementById('regStep1').style.display = 'block';
    document.getElementById('regStep2').style.display = 'none';
    document.getElementById('registerError').style.display = 'none';
    document.getElementById('registerSuccess').style.display = 'none';
    document.getElementById('regCode').value = '';
    document.getElementById('regPassword').value = '';
    
    // Загружаем сохранённые данные гостя
    const savedData = localStorage.getItem('guest_init_data');
    if (savedData) {
        try {
            const data = JSON.parse(savedData);
            if (data.name) {
                document.getElementById('regName').value = data.name;
            }
            if (data.birth_date) {
                document.getElementById('regBirthDate').value = data.birth_date;
            }
        } catch(e) {}
    }
}

function closeRegisterModal() {
    document.getElementById('registerModal').classList.remove('active');
}

async function requestCall() {
    const phone = document.getElementById('regPhone').value.replace(/\D/g, '');
    if (phone.length < 10) {
        showRegisterError('Введите корректный номер телефона');
        return;
    }
    
    const btn = document.querySelector('#regStep1 button');
    btn.disabled = true;
    btn.textContent = 'Звоним...';
    
    try {
        const res = await fetch('/api/auth/request-call', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone: phone })
        });
        const data = await res.json();
        
        if (data.success) {
            document.getElementById('regStep1').style.display = 'none';
            document.getElementById('regStep2').style.display = 'block';
            showRegisterSuccess('Звонок совершён! Введите последние 4 цифры номера.');
        } else {
            showRegisterError(data.error || 'Не удалось совершить звонок');
            btn.disabled = false;
            btn.textContent = 'Получить код ✨';
        }
    } catch(e) {
        showRegisterError('Ошибка соединения');
        btn.disabled = false;
        btn.textContent = 'Получить код ✨';
    }
}

function showRegisterError(msg) {
    const el = document.getElementById('registerError');
    el.textContent = msg;
    el.style.display = 'block';
    document.getElementById('registerSuccess').style.display = 'none';
}

function showRegisterSuccess(msg) {
    const el = document.getElementById('registerSuccess');
    el.textContent = msg;
    el.style.display = 'block';
    document.getElementById('registerError').style.display = 'none';
}

async function submitRegister(e) {
    e.preventDefault();
    
    const phone = document.getElementById('regPhone').value.replace(/\D/g, '');
    const code = document.getElementById('regCode').value.trim();
    const name = document.getElementById('regName').value.trim();
    const birthDate = document.getElementById('regBirthDate').value;
    const password = document.getElementById('regPassword').value;
    const passwordConfirm = document.getElementById('regPasswordConfirm').value;
    const passwordError = document.getElementById('regPasswordError');
    
    if (!name) {
        showRegisterError('Введите имя');
        return;
    }
    
    // Проверка совпадения паролей
    if (password !== passwordConfirm) {
        passwordError.style.display = 'block';
        return;
    }
    passwordError.style.display = 'none';
    
    // Валидация пароля
    if (password.length < 8) {
        showRegisterError('Пароль должен быть не менее 8 символов');
        return;
    }
    if (!/^[A-ZА-ЯЁ]/.test(password)) {
        showRegisterError('Первая буква пароля должна быть заглавной');
        return;
    }
    if (!/\d+$/.test(password)) {
        showRegisterError('Пароль должен заканчиваться цифрами');
        return;
    }
    
    // Проверка кода
    if (!/^\d{4}$/.test(code)) {
        showRegisterError('Введите ровно 4 цифры');
        return;
    }
    
    // Проверка согласия на обработку ПД
    if (!document.getElementById('regConsent').checked) {
        showRegisterError('Необходимо согласие на обработку персональных данных');
        return;
    }

    if (!document.getElementById('regTransferConsent').checked) {
        showRegisterError('Необходимо согласие на трансграничную передачу данных');
        return;
    }
        
    try {
        const res = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone: phone, code: code, password: password, name: name, birth_date: birthDate })
        });

        const data = await res.json();
        
        if (data.success) {
            closeRegisterModal();
            window.location.reload();
        } else {
            showRegisterError(data.error || 'Ошибка регистрации');
        }
    } catch(e) {
        showRegisterError('Ошибка соединения');
    }
}

// ============================================
// ОБНОВЛЁННЫЙ ЛОГИН (телефон + пароль, не закрывается при ошибке)
// ============================================

async function submitLogin(e) {
    e.preventDefault();
    
    if (!document.getElementById('loginConsent').checked) {
        document.getElementById('loginError').textContent = 'Необходимо согласие на обработку персональных данных';
        document.getElementById('loginError').style.display = 'block';
        return;
    }
    
    const phone = document.getElementById('loginPhone').value.replace(/\D/g, '');
    const password = document.getElementById('loginPassword').value;
    const errorEl = document.getElementById('loginError');
    
    errorEl.style.display = 'none';
    
    try {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone: phone, password: password })
        });
        const data = await res.json();
        
        if (data.success) {
            closeAuthModal();
            window.location.reload();
        } else {
            errorEl.textContent = data.error || 'Неверный телефон или пароль';
            errorEl.style.display = 'block';
            // Очищаем только пароль, телефон оставляем
            document.getElementById('loginPassword').value = '';
        }
    } catch(e) {
        errorEl.textContent = 'Ошибка соединения';
        errorEl.style.display = 'block';
    }
}

// ============================================
// КАРТА ДНЯ
// ============================================

function openDailyCardModal(autoFlip = false) {
    const modal = document.getElementById('dailyCardModal');
    modal.classList.add('active');
    showLoading();
    fetchDailyCard(autoFlip);
}

function closeDailyCardModal() {
    document.getElementById('dailyCardModal').classList.remove('active');
}

function initDailyCardModal() {
    const overlay = document.getElementById('dailyCardModal');
    if (overlay) {
        overlay.addEventListener('click', e => { if (e.target === overlay) closeDailyCardModal(); });
    }
}

// ============================================
// КАРТА ДНЯ — SSE-стрим (A3)
// ============================================

/**
 * Оболочка карты дня: рисует анимацию, карту, базовое значение.
 * AI-толкование — пустой контейнер #dailyCardAiText, который наполняется
 * по чанкам. Рендерится сразу после meta — до того, как придёт AI-текст.
 */
function renderDailyCardShell(meta, autoFlip = false) {
    const container = document.getElementById('dailyCardContent');
    container.innerHTML = `
        <div class="daily-card-wrapper">
            <div class="card-deck" id="cardDeck">
                <div class="deck-card deck-card-1"></div>
                <div class="deck-card deck-card-2"></div>
                <div class="deck-card deck-card-3"></div>
                <div class="deck-card deck-card-4"></div>
                <div class="deck-card deck-card-5"></div>
            </div>
            
            <div class="flying-card vibrating" id="flyingCard" onclick="flipDailyCard()">
                <div class="flying-card-inner ${autoFlip ? 'flipped' : ''}">
                    <div class="card-front">
                        <img src="/static/images/tarot/80.jpg" alt="Таро" style="width:100%;height:100%;object-fit:cover;border-radius:14px;">
                    </div>
                    <div class="card-back">
                        <div class="card-face-icon">
                            <img src="/static/images/tarot/${String(meta.id + 2).padStart(2, '0')}.jpg" alt="${sanitizeHTML(meta.name)}" style="width:100%;height:100%;object-fit:cover;border-radius:14px;">
                        </div>
                    </div>
                </div>
            </div>
            
            <p class="card-hint" id="cardHint" style="${autoFlip ? 'display:none;' : ''}">Нажми на карту</p>
            
            <div class="daily-card-text" id="dailyCardText" style="${autoFlip ? 'display:block;' : 'display:none;'}">
                <h3 style="color:var(--color-gold);font-size:18px;margin-bottom:8px;">${sanitizeHTML(meta.name)}</h3>
                <p style="font-size:14px;color:var(--color-text);line-height:1.6;margin-bottom:8px;">${sanitizeHTML(meta.meaning)}</p>
                ${meta.advice ? '<p style="font-size:13px;color:var(--color-gold);font-style:italic;">' + sanitizeHTML(meta.advice) + '</p>' : ''}
                <span class="result-highlight" style="margin-top:8px;">Карта дня • ${sanitizeHTML(meta.date)}</span>
                <p id="dailyCardAiText" class="result-text"></p>
            </div>
        </div>`;

    setTimeout(() => {
        const deck = document.getElementById('cardDeck');
        const card = document.getElementById('flyingCard');
        if (deck) deck.classList.add('deck-open');
        if (card) {
            setTimeout(() => {
                card.classList.add('card-fly-out');
                if (autoFlip) {
                    card.classList.remove('vibrating');
                    setTimeout(() => {
                        const text = document.getElementById('dailyCardText');
                        if (text) text.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }, 600);
                }
            }, 400);
        }
    }, 300);
}

async function fetchDailyCard(autoFlip = false) {
    const container = document.getElementById('dailyCardContent');
    let shellRendered = false;

    await streamPost(
        '/api/tarot/daily/stream',
        {},
        {
            onMeta: function(meta) {
                // Карта выпала: сразу рисуем оболочку. Дальше — только AI-текст.
                hideLoading();
                renderDailyCardShell(meta, autoFlip);
                shellRendered = true;
            },
            onChunk: function(data) {
                // Наполняем #dailyCardAiText по чанкам. Если контейнера ещё нет —
                // игнорируем (значит meta ещё не пришла, такого быть не должно).
                const el = document.getElementById('dailyCardAiText');
                if (el) el.textContent += (data.chunk || '');
            },
            onError: function() {
                hideLoading();
                if (!shellRendered) {
                    container.innerHTML = '<p>Магия пока недоступна. Попробуй позже</p>';
                }
            },
        }
    );
}

function renderDailyCard(data, autoFlip = false) {
    const container = document.getElementById('dailyCardContent');
    container.innerHTML = `
        <div class="daily-card-wrapper">
            <div class="card-deck" id="cardDeck">
                <div class="deck-card deck-card-1"></div>
                <div class="deck-card deck-card-2"></div>
                <div class="deck-card deck-card-3"></div>
                <div class="deck-card deck-card-4"></div>
                <div class="deck-card deck-card-5"></div>
            </div>
            
            <div class="flying-card vibrating" id="flyingCard" onclick="flipDailyCard()">
                <div class="flying-card-inner ${autoFlip ? 'flipped' : ''}">
                    <div class="card-front">
                        <img src="/static/images/tarot/80.jpg" alt="Таро" style="width:100%;height:100%;object-fit:cover;border-radius:14px;">
                    </div>
                    <div class="card-back">
                        <div class="card-face-icon">
                            <img src="/static/images/tarot/${String(data.id + 2).padStart(2, '0')}.jpg" alt="${sanitizeHTML(data.name)}" style="width:100%;height:100%;object-fit:cover;border-radius:14px;">
                        </div>
                    </div>
                </div>
            </div>
            
            <p class="card-hint" id="cardHint" style="${autoFlip ? 'display:none;' : ''}">Нажми на карту</p>
            
            <div class="daily-card-text" id="dailyCardText" style="${autoFlip ? 'display:block;' : 'display:none;'}">
                <h3 style="color:var(--color-gold);font-size:18px;margin-bottom:8px;">${sanitizeHTML(data.name)}</h3>
                <p style="font-size:14px;color:var(--color-text);line-height:1.6;margin-bottom:8px;">${sanitizeHTML(data.meaning)}</p>
                ${data.advice ? '<p style="font-size:13px;color:var(--color-gold);font-style:italic;">' + sanitizeHTML(data.advice) + '</p>' : ''}
                <span class="result-highlight" style="margin-top:8px;">Карта дня • ${sanitizeHTML(data.date)}</span>
                ${data.ai_interpretation ? '<p class="result-text">' + sanitizeHTML(data.ai_interpretation) + '</p>' : ''}
            </div>
        </div>`;

    setTimeout(() => {
        const deck = document.getElementById('cardDeck');
        const card = document.getElementById('flyingCard');
        if (deck) deck.classList.add('deck-open');
        if (card) {
            setTimeout(() => {
                card.classList.add('card-fly-out');
                if (autoFlip) {
                    card.classList.remove('vibrating');
                    setTimeout(() => {
                        const text = document.getElementById('dailyCardText');
                        if (text) text.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }, 600);
                }
            }, 400);
        }
    }, 300);
}

function flipDailyCard() {
    const inner = document.querySelector('#flyingCard .flying-card-inner');
    const text = document.getElementById('dailyCardText');
    const hint = document.getElementById('cardHint');
    const card = document.getElementById('flyingCard');
    
    if (inner) inner.classList.toggle('flipped');
    if (text) text.style.display = inner.classList.contains('flipped') ? 'block' : 'none';
    if (hint) hint.style.display = 'none';
    if (card) card.classList.remove('vibrating');
}

// ============================================
// LOADING
// ============================================

// Факты для прелоадера
const UNANUM_FACTS = [
    'Число жизненного пути — ваш главный навигатор. Unanum рассчитает его по дате рождения и покажет, куда двигаться',
    'Не знаете время рождения? Unanum построит натальную карту на полдень — асцендент будет приблизительным, но планеты в знаках точны',
    'Каждый лунный день имеет свой ритуал. На Unanum они описаны с конкретными действиями и предметами',
    'В денежном коде каждая цифра отвечает за свой аспект финансов. Unanum расшифровывает все четыре',
    'Хотите проверить совместимость с кем угодно? Введите два имени и две даты рождения — Unanum покажет процент и 7 критериев',
    'AI-проводница unanum говорит без «ты» и «вы» — только по имени или безлично. Как мудрая подруга',
    'Психоматрица покажет не только ваши сильные стороны. Пустые ячейки — это зоны, которые можно развить осознанно',
    'Таро на unanum — это не только карта дня. Вы можете сделать расклад из трёх карт и получить AI-толкование',
    'График жизни строится без искусственного дополнения до семи цифр. Сколько цифр в коде — столько и периодов',
    'Каждый пункт на unanum заканчивается вопросом? Ответ на него есть в полной версии',
    'В справочнике чисел unanum собраны описания для всех шести нумерологических категорий — от Жизненного Пути до Дня Рождения',
    'Unanum не требует веры в магию. Это игра, которая помогает посмотреть на себя с неожиданной стороны'
];

let waitingGameInterval = null;
let currentFactIndex = 0;

function showWaitingGame() {
    const loadingEl = document.getElementById('loadingOverlay');
    if (!loadingEl) return;
    
    let gameType = Math.floor(Math.random() * 3);
    const loaderContent = loadingEl.querySelector('.crystal-loader');
    if (!loaderContent) return;
    
    if (gameType === 0) {
        currentFactIndex = Math.floor(Math.random() * UNANUM_FACTS.length);
        
        const factsContainer = document.createElement('div');
        factsContainer.id = 'waitingFacts';
        factsContainer.style.cssText = 'margin-top:16px;max-width:320px;text-align:center;';
        factsContainer.innerHTML = `
            <p style="font-size:14px;color:var(--color-text-light);margin-bottom:4px;">Ответ стоит того, чтобы подождать</p>
            <p style="font-size:12px;color:var(--color-text-lighter);margin-bottom:10px;">Обычно это занимает до минуты. А пока — интересное о unanum:</p>
            <div style="display:flex;align-items:center;gap:0;">
                <div onclick="prevFact()" style="width:40px;height:100px;display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0;-webkit-tap-highlight-color:transparent;">
                    <span style="font-size:20px;color:var(--color-gold);user-select:none;">◀</span>
                </div>
                <div id="factCard" style="flex:1;background:rgba(30,58,30,0.6);border:1px solid var(--color-border);border-radius:12px;padding:16px;min-height:80px;display:flex;align-items:center;justify-content:center;transition:opacity 0.4s ease;">
                    <p id="factText" style="font-size:14px;color:var(--color-text-light);line-height:1.6;margin:0;text-align:center;">${UNANUM_FACTS[currentFactIndex]}</p>
                </div>
                <div onclick="nextFact()" style="width:40px;height:100px;display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0;-webkit-tap-highlight-color:transparent;">
                    <span style="font-size:20px;color:var(--color-gold);user-select:none;">▶</span>
                </div>
            </div>
            <div id="factDots" style="margin-top:10px;display:flex;gap:6px;justify-content:center;">
                ${UNANUM_FACTS.map((_, i) => `<span style="width:8px;height:8px;border-radius:50%;background:${i === currentFactIndex ? 'var(--color-gold)' : 'var(--color-border)'};display:inline-block;transition:background 0.3s ease;"></span>`).join('')}
            </div>
        `;
        loaderContent.appendChild(factsContainer);
        
        waitingGameInterval = setInterval(() => {
            currentFactIndex = (currentFactIndex + 1) % UNANUM_FACTS.length;
            const factText = document.getElementById('factText');
            const factCard = document.getElementById('factCard');
            if (factText && factCard) {
                factCard.style.opacity = '0';
                setTimeout(() => {
                    factText.textContent = UNANUM_FACTS[currentFactIndex];
                    factCard.style.opacity = '1';
                }, 300);
            }
            const dots = document.querySelectorAll('#factDots span');
            dots.forEach((dot, i) => {
                dot.style.background = i === currentFactIndex ? 'var(--color-gold)' : 'var(--color-border)';
            });
        }, 4000);
        
    } else if (gameType === 1) {
        // Вариант 2: Справочник чисел
        const refContainer = document.createElement('div');
        refContainer.id = 'waitingRef';
        refContainer.style.cssText = 'margin-top:16px;max-width:320px;text-align:center;';
        
        let numbersHtml = '';
        [1,2,3,4,5,6,7,8,9,11,22,33].forEach(n => {
            numbersHtml += `<span onclick="showMiniNumberInfo(${n})" style="display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:50%;background:rgba(255,213,79,0.08);color:var(--color-gold);font-weight:600;font-size:14px;cursor:pointer;border:1px solid rgba(255,213,79,0.2);margin:4px;transition:all 0.2s ease;" onmouseover="this.style.background='var(--color-gold)';this.style.color='#0f1f0f';" onmouseout="this.style.background='rgba(255,213,79,0.08)';this.style.color='var(--color-gold)';">${n}</span>`;
        });
        
        refContainer.innerHTML = `
            <p style="font-size:13px;color:var(--color-text-lighter);margin-bottom:8px;">Изучите значения чисел:</p>
            <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:2px;margin-bottom:12px;">${numbersHtml}</div>
            <div id="miniNumberInfo" style="background:rgba(30,58,30,0.6);border:1px solid var(--color-border);border-radius:12px;padding:16px;min-height:60px;display:flex;align-items:center;justify-content:center;">
                <p style="font-size:14px;color:var(--color-text-light);line-height:1.6;margin:0;">Нажмите на число, чтобы узнать его значение</p>
            </div>
        `;
        loaderContent.appendChild(refContainer);

    } else if (gameType === 2) {
        // Вариант 3: Угадай число
        if (typeof NUMBER_DATA === 'undefined' || !NUMBER_DATA.life_path) {
            // Fallback: если данные не загружены, показываем факты
            gameType = 0;
            showWaitingGame();
            return;
        }
        
        const gameContainer = document.createElement('div');
        gameContainer.id = 'waitingGame';
        gameContainer.style.cssText = 'margin-top:16px;max-width:320px;text-align:center;';
        
        // Выбираем 3 случайных числа для раундов
        const allNumbers = [1,2,3,4,5,6,7,8,9,11,22,33];
        const shuffled = allNumbers.sort(() => Math.random() - 0.5);
        const roundNumbers = shuffled.slice(0, 3);
        
        window._guessGame = {
            round: 0,
            score: 0,
            numbers: roundNumbers,
            totalRounds: 3
        };
        
        gameContainer.innerHTML = `
            <p style="font-size:14px;color:var(--color-text-light);margin-bottom:4px;">✨ Ответ стоит того, чтобы подождать</p>
            <p style="font-size:12px;color:var(--color-text-lighter);margin-bottom:10px;">Угадайте число, пока готовится разбор</p>
            <div id="gameScore" style="font-size:12px;color:var(--color-gold);margin-bottom:8px;">Верно: 0 из 0</div>
            <div id="gameCard" style="background:rgba(30,58,30,0.6);border:1px solid var(--color-border);border-radius:12px;padding:16px;min-height:80px;display:flex;align-items:center;justify-content:center;margin-bottom:12px;">
                <p id="gameDesc" style="font-size:14px;color:var(--color-text-light);line-height:1.6;margin:0;text-align:center;">Загрузка...</p>
            </div>
            <div id="gameOptions" style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap;"></div>
        `;
        loaderContent.appendChild(gameContainer);
        
        renderGuessRound();
    }

}

function hideWaitingGame() {
    if (waitingGameInterval) {
        clearInterval(waitingGameInterval);
        waitingGameInterval = null;
    }
    const factsEl = document.getElementById('waitingFacts');
    if (factsEl) factsEl.remove();
    const refEl = document.getElementById('waitingRef');
    if (refEl) refEl.remove();
    const gameEl = document.getElementById('waitingGame');
    if (gameEl) gameEl.remove();
    window._guessGame = null;
}

function prevFact() {
    currentFactIndex = (currentFactIndex - 1 + UNANUM_FACTS.length) % UNANUM_FACTS.length;
    updateFactDisplay();
}

function nextFact() {
    currentFactIndex = (currentFactIndex + 1) % UNANUM_FACTS.length;
    updateFactDisplay();
}

function updateFactDisplay() {
    const factText = document.getElementById('factText');
    const factCard = document.getElementById('factCard');
    if (factText && factCard) {
        factCard.style.opacity = '0';
        setTimeout(() => {
            factText.textContent = UNANUM_FACTS[currentFactIndex];
            factCard.style.opacity = '1';
        }, 300);
    }
    const dots = document.querySelectorAll('#factDots span');
    dots.forEach((dot, i) => {
        dot.style.background = i === currentFactIndex ? 'var(--color-gold)' : 'var(--color-border)';
    });
}

function showLoading() { 
    document.getElementById('loadingOverlay').classList.add('active'); 
    setTimeout(showWaitingGame, 100);
}
function hideLoading() { 
    document.getElementById('loadingOverlay').classList.remove('active'); 
    hideWaitingGame();
}

function showMiniNumberInfo(num) {
    const infoDiv = document.getElementById('miniNumberInfo');
    if (!infoDiv) return;
    
    let description = '';
    if (typeof NUMBER_DATA !== 'undefined' && NUMBER_DATA.life_path && NUMBER_DATA.life_path.numbers[num]) {
        const data = NUMBER_DATA.life_path.numbers[num];
        description = `<strong>${num} — ${data.subtitle}</strong><br><span style="font-size:12px;">${data.meaning}</span>`;
    } else {
        const simple = {
            1: 'Лидер. Независимость, инициатива, смелость.',
            2: 'Миротворец. Дипломатия, чувствительность, партнёрство.',
            3: 'Творец. Творчество, общение, радость.',
            4: 'Строитель. Стабильность, дисциплина, порядок.',
            5: 'Искатель. Свобода, приключения, перемены.',
            6: 'Хранитель. Забота, ответственность, гармония.',
            7: 'Мудрец. Анализ, интуиция, познание.',
            8: 'Управитель. Власть, изобилие, достижения.',
            9: 'Гуманист. Сострадание, служение, завершение.',
            11: 'Мастер-вдохновитель. Интуиция, духовность.',
            22: 'Мастер-созидатель. Масштаб, стратегия.',
            33: 'Мастер-учитель. Любовь, исцеление, служение.'
        };
        description = `<strong>${num} — ${simple[num] || 'Уникальное число'}</strong>`;
    }
    
    infoDiv.innerHTML = `<p style="font-size:14px;color:var(--color-text-light);line-height:1.6;margin:0;">${description}</p>`;
}

function renderGuessRound() {
    const game = window._guessGame;
    if (!game || game.round >= game.totalRounds) return;
    
    const num = game.numbers[game.round];
    const data = NUMBER_DATA.life_path.numbers[num];
    if (!data) return;
    
    // Показываем описание
    const descEl = document.getElementById('gameDesc');
    if (descEl) {
        descEl.textContent = data.meaning.substring(0, 120) + '...';
    }
    
    // Генерируем варианты ответов (правильный + 3 случайных)
    const allNumbers = [1,2,3,4,5,6,7,8,9,11,22,33];
    const wrongOptions = allNumbers.filter(n => n !== num).sort(() => Math.random() - 0.5).slice(0, 3);
    const options = [num, ...wrongOptions].sort(() => Math.random() - 0.5);
    
    const optionsEl = document.getElementById('gameOptions');
    if (optionsEl) {
        optionsEl.innerHTML = options.map(opt => 
            `<button class="btn btn-outline btn-sm" onclick="guessNumber(${opt}, ${num})" style="min-width:50px;font-size:16px;font-weight:600;">${opt}</button>`
        ).join('');
    }
    
    const scoreEl = document.getElementById('gameScore');
    if (scoreEl) {
        scoreEl.textContent = `Верно: ${game.score} из ${game.round}`;
    }
}

function guessNumber(guessed, correct) {
    const game = window._guessGame;
    if (!game) return;
    
    const buttons = document.querySelectorAll('#gameOptions button');
    buttons.forEach(btn => {
        const val = parseInt(btn.textContent);
        btn.disabled = true;
        if (val === correct) {
            btn.style.background = '#7eb89e';
            btn.style.color = '#0f1f0f';
            btn.style.borderColor = '#7eb89e';
        } else if (val === guessed) {
            btn.style.background = '#d4838a';
            btn.style.color = '#0f1f0f';
            btn.style.borderColor = '#d4838a';
        }
    });
    
    if (guessed === correct) {
        game.score++;
    }
    game.round++;
    
    const scoreEl = document.getElementById('gameScore');
    if (scoreEl) {
        scoreEl.textContent = `Верно: ${game.score} из ${game.round}`;
    }
    
    if (game.round >= game.totalRounds) {
        // Конец игры
        setTimeout(() => {
            const gameCard = document.getElementById('gameCard');
            const gameOptions = document.getElementById('gameOptions');
            if (gameCard) {
                gameCard.innerHTML = `<p style="font-size:16px;color:var(--color-gold);text-align:center;">Вы угадали ${game.score} из ${game.totalRounds}! 🎉</p>`;
            }
            if (gameOptions) {
                gameOptions.innerHTML = '';
            }
        }, 1000);
    } else {
        // Следующий раунд
        setTimeout(renderGuessRound, 1500);
    }
}

// ============================================
// ТАБ-БАР
// ============================================

function initTabBar() {
    const tabs = document.querySelectorAll('.tab-item[data-tab]');
    const currentPath = window.location.pathname;
    tabs.forEach(tab => {
        tab.classList.remove('active');
        if (tab.dataset.tab === 'home' && (currentPath === '/' || currentPath === '/index')) {
            tab.classList.add('active');
        }
        if (tab.dataset.tab === 'library' && currentPath.includes('/tarot/library')) {
            tab.classList.add('active');
        }
        if (tab.dataset.tab === 'profile' && currentPath.includes('/profile')) {
            tab.classList.add('active');
        }
    });
}

// ============================================
// ФОРМАТИРОВАНИЕ РЕЗУЛЬТАТОВ
// ============================================

function formatResult(data) {
    if (data.error) return `<p style="color:var(--color-error);">${sanitizeHTML(data.message || data.error)}</p>`;
    if (data.code && data.digits_breakdown) return formatFinancialCode(data);
    if (data.emoji && data.daily) return formatHoroscope(data);
    if (data.compatibility_percent) return formatCompatibility(data);
    if (data.phase && data.lunar_day) return formatMoon(data);
    if (data.message) return formatNatal(data);
    if (data.meaning) return `<p class="result-text">${sanitizeHTML(data.meaning)}</p>`;
    if (data.interpretation) return `<p class="result-text">${sanitizeHTML(data.interpretation)}</p>`;
    if (data.daily_message) return `<span class="result-highlight">${sanitizeHTML(data.sign)} • ${sanitizeHTML(data.date)}</span><p class="result-text">${sanitizeHTML(data.daily_message)}</p>`;
    if (data.destiny_number) return `<span class="result-highlight">Число судьбы: ${data.destiny_number}</span>`;
    if (data.lunar_day && data.phase_name) return formatMoonDetail(data);
    return '<p class="result-text">Результат готов</p>';
}

function formatFinancialCode(data) {
    let html = '';
    html += `<div class="result-code" style="font-size:50px;">${sanitizeHTML(data.code)}</div>`;
    html += `<div class="result-label">Твой денежный код</div>`;
    html += '<div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin:12px 0;">';
    const isPaid = window.userTariff === 'Пламя';
    data.digits_breakdown.forEach(d => {
        const text = isPaid ? (d.meaning || '') : (d.teaser || d.meaning || '');
        let displayText = text;
        if (!isPaid && d.teaser) {
            const sentences = text.split('. ');
            if (sentences.length >= 3 && (sentences[0].includes('(Лидер)') || sentences[0].includes('(Движение)') || sentences[0].includes('(Завершение)') || sentences[0].includes('(Забота)') || sentences[0].includes('—'))) {
                displayText = sentences.slice(1).join('. ');
            }
        }
        html += `<div style="text-align:center;min-width:65px;">
            <div style="font-size:24px;font-weight:600;color:var(--color-gold);">${d.digit}</div>
            <div style="font-size:10px;color:var(--color-text-lighter);">${sanitizeHTML(d.position)}</div>
            <div style="font-size:11px;color:var(--color-text-light);line-height:1.4;">${sanitizeHTML(displayText)}</div>
            ${!isPaid ? '<div style="margin-top:4px;font-size:10px;color:var(--color-gold);cursor:pointer;" onclick="showPaywall()">Читать полностью →</div>' : ''}
        </div>`;
    });
    html += '</div>';

    if (data.ai_summary) {
        if (isPaid) {
            html += `<blockquote style="border-left:3px solid var(--color-gold);margin:16px 0;padding:8px 16px;font-size:14px;color:var(--color-text-light);line-height:1.6;">${sanitizeHTML(data.ai_summary)}</blockquote>`;
        } else {
            let shortText = data.ai_summary;
            if (shortText.includes('Итоговая рекомендация')) {
                shortText = shortText.split('Итоговая рекомендация')[0].trim() + '...';
            }
            shortText += ' <span style="color:var(--color-gold);cursor:pointer;text-decoration:underline;" onclick="showPaywall()">Читать полностью →</span>';
            html += `<blockquote style="border-left:3px solid var(--color-gold);margin:16px 0;padding:8px 16px;font-size:14px;color:var(--color-text-light);line-height:1.6;">${shortText}</blockquote>`;
        }
    }

    // Бесплатный: показываем названия платных секций с интригой (всегда, даже если данные не сгенерированы)
    if (!isPaid) {
        const premiumBlocks = [
            { title: 'Подробный анализ кода', teaser: data.detailed_teaser || data.detailed_analysis_teaser || 'Как цифры взаимодействуют между собой и какая из них главная — ответ меняет стратегию заработка.' },
            { title: 'Связь с Числом Жизненного Пути', teaser: data.life_path_link_teaser || 'Два ключевых числа могут усиливать друг друга или создавать скрытый конфликт.' },
            { title: 'Персональные рекомендации', teaser: data.personal_recs_teaser || 'Три конкретных шага, основанных на ваших числах. Один из них способен удвоить доход.' },
            { title: 'Финансовый прогноз на 3 года', teaser: data.oracle_forecast_teaser || 'Что ждать в ближайшие годы — каждый год несёт свою энергию.' },
            { title: 'Персональный денежный ритуал', teaser: data.oracle_rituals_teaser || 'Ритуал, построенный на цифрах вашего кода и текущем лунном дне.' },
            { title: 'Полный нумерологический разбор', teaser: data.oracle_full_teaser || 'Как все числа работают вместе.' },
        ];
        
        html += '<div style="margin-top:20px;">';
        premiumBlocks.forEach(block => {
            html += `<div style="margin-bottom:14px;">
                <span style="font-size:14px;color:var(--color-gold);font-weight:600;">🔒 ${block.title}</span>
                <p style="font-size:12px;color:var(--color-text-lighter);margin:4px 0 0 0;line-height:1.5;">${block.teaser}</p>
            </div>`;
        });
        html += '<button class="btn btn-share" onclick="showPaywall()" style="width:100%;margin-top:8px;">Открыть всё — ' + (window.paywallPrice || 599) + ' ₽</button>';
        html += '</div>';
    }

    // Платный: показываем полные тексты всех секций
    if (isPaid) {
        if (data.detailed_analysis) {
            html += `<div style="margin-top:16px;"><span style="color:var(--color-gold);font-weight:600;">Подробный анализ</span><p style="font-size:14px;color:var(--color-text-light);line-height:1.6;">${sanitizeHTML(data.detailed_analysis)}</p></div>`;
        }
        if (data.life_path_link) {
            html += `<div style="margin-top:16px;"><span style="color:var(--color-gold);font-weight:600;">Связь с Числом Жизненного Пути</span><p style="font-size:14px;color:var(--color-text-light);line-height:1.6;">${sanitizeHTML(data.life_path_link)}</p></div>`;
        }
        if (data.personal_recommendations) {
            html += `<div style="margin-top:16px;"><span style="color:var(--color-gold);font-weight:600;">Персональные рекомендации</span>`;
            data.personal_recommendations.forEach(r => {
                html += `<p style="font-size:14px;color:var(--color-text-light);line-height:1.6;">— ${sanitizeHTML(r)}</p>`;
            });
            html += `</div>`;
        }
        if (data.oracle_forecast) {
            html += `<div style="margin-top:16px;"><span style="color:var(--color-gold);font-weight:600;">Финансовый прогноз по годам</span>`;
            data.oracle_forecast.forEach(f => {
                html += `<p style="font-size:14px;color:var(--color-text-light);line-height:1.6;"><strong>${f.year} год:</strong> ${sanitizeHTML(f.text)}</p>`;
            });
            html += `</div>`;
        }
        if (data.oracle_rituals) {
            html += `<div style="margin-top:16px;"><span style="color:var(--color-gold);font-weight:600;">Персональный денежный ритуал</span><p style="font-size:14px;color:var(--color-text-light);line-height:1.6;">${sanitizeHTML(data.oracle_rituals)}</p></div>`;
        }
        if (data.oracle_full_analysis) {
            html += `<div style="margin-top:16px;"><span style="color:var(--color-gold);font-weight:600;">Полный нумерологический разбор</span><p style="font-size:14px;color:var(--color-text-light);line-height:1.6;">${sanitizeHTML(data.oracle_full_analysis)}</p></div>`;
        }
    }
    return html;
}

function formatHoroscope(data) {
    let html = '';
    if (data.emoji) {
        const signToSvgKey = {
            'Овен': 'aries', 'Телец': 'taurus', 'Близнецы': 'gemini',
            'Рак': 'cancer', 'Лев': 'leo', 'Дева': 'virgo',
            'Весы': 'libra', 'Скорпион': 'scorpio', 'Стрелец': 'sagittarius',
            'Козерог': 'capricorn', 'Водолей': 'aquarius', 'Рыбы': 'pisces'
        };
        const svgKey = signToSvgKey[data.sign] || 'aries';
        
        html += `<div style="text-align:center;margin:12px 0;">
            <div class="horoscope-sign-svg">${zodiacSvgs[svgKey]}</div>
            <div style="font-size:22px;font-weight:600;color:var(--color-text);">${sanitizeHTML(data.sign)}</div>
            <div style="font-size:13px;color:var(--color-text-lighter);">${sanitizeHTML(data.element)} • ${sanitizeHTML(data.period)}</div>
        </div>`;
        if (data.description) {
            html += `<p style="font-size:11px;color:var(--color-text-lighter);text-align:center;margin-bottom:16px;">${sanitizeHTML(data.description)}</p>`;
        }

        // Дополнительная информация о знаке
        if (data.extra) {
            html += `<div style="display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-bottom:16px;">`;
            if (data.extra.color) {
                html += `<span style="font-size:11px;color:var(--color-text-light);background:rgba(30,58,30,0.6);padding:4px 10px;border-radius:12px;border:1px solid var(--color-border);">Цвет: ${sanitizeHTML(data.extra.color)}</span>`;
            }
            if (data.extra.lucky_day) {
                html += `<span style="font-size:11px;color:var(--color-text-light);background:rgba(30,58,30,0.6);padding:4px 10px;border-radius:12px;border:1px solid var(--color-border);">Удачный день: ${sanitizeHTML(data.extra.lucky_day)}</span>`;
            }
            if (data.extra.unlucky_day) {
                html += `<span style="font-size:11px;color:var(--color-text-light);background:rgba(30,58,30,0.6);padding:4px 10px;border-radius:12px;border:1px solid var(--color-border);">Неудачный день: ${sanitizeHTML(data.extra.unlucky_day)}</span>`;
            }
            if (data.extra.stone) {
                html += `<span style="font-size:11px;color:var(--color-text-light);background:rgba(30,58,30,0.6);padding:4px 10px;border-radius:12px;border:1px solid var(--color-border);">Камень: ${sanitizeHTML(data.extra.stone)}</span>`;
            }
            if (data.extra.lucky_number) {
                html += `<span style="font-size:11px;color:var(--color-text-light);background:rgba(30,58,30,0.6);padding:4px 10px;border-radius:12px;border:1px solid var(--color-border);">Число удачи: ${sanitizeHTML(data.extra.lucky_number)}</span>`;
            }
            html += `</div>`;
        }
        const isPaid = window.userTariff === 'Пламя';

        if (data.love || data.love_teaser) {
            const text = isPaid ? data.love : (data.love_teaser || data.love);
            html += `<div style="margin-top:14px;"><span style="font-weight:600;color:var(--color-gold);">Любовь и отношения</span></div>`;
            html += `<p class="result-text" style="margin-top:4px;">${sanitizeHTML(text)}</p>`;
            if (!isPaid) html += '<div style="margin-top:4px;font-size:10px;color:var(--color-gold);cursor:pointer;" onclick="showPaywall()">Читать полностью →</div>';
        }
        if (data.career || data.career_teaser) {
            const text = isPaid ? data.career : (data.career_teaser || data.career);
            html += `<div style="margin-top:14px;"><span style="font-weight:600;color:var(--color-gold);">Карьера и финансы</span></div>`;
            html += `<p class="result-text" style="margin-top:4px;">${sanitizeHTML(text)}</p>`;
            if (!isPaid) html += '<div style="margin-top:4px;font-size:10px;color:var(--color-gold);cursor:pointer;" onclick="showPaywall()">Читать полностью →</div>';
        }
        if (data.health || data.health_teaser) {
            const text = isPaid ? data.health : (data.health_teaser || data.health);
            html += `<div style="margin-top:14px;"><span style="font-weight:600;color:var(--color-gold);">Здоровье</span></div>`;
            html += `<p class="result-text" style="margin-top:4px;">${sanitizeHTML(text)}</p>`;
            if (!isPaid) html += '<div style="margin-top:4px;font-size:10px;color:var(--color-gold);cursor:pointer;" onclick="showPaywall()">Читать полностью →</div>';
        }
    }
    return html;
}

function formatMoon(data) {
    let html = '';
    html += `<div class="result-code" style="font-size:22px;letter-spacing:2px;">${sanitizeHTML(data.phase)}</div>`;
    html += `<div class="result-label">${data.lunar_day}-й лунный день</div>`;
    html += `<p class="result-text">${sanitizeHTML(data.recommendation)}</p>`;
    return html;
}

function formatMoonDetail(data) {
    let html = '';
    if (data.phase_name) {
        html += `<div class="result-code" style="font-size:22px;letter-spacing:2px;">${sanitizeHTML(data.phase_name)}</div>`;
    }
    if (data.lunar_day) {
        html += `<div class="result-label">${data.lunar_day}-й лунный день</div>`;
    }
    if (data.moon_zodiac) {
        html += `<p style="font-size:12px;color:var(--color-text-lighter);text-align:center;">Луна в знаке: ${sanitizeHTML(data.moon_zodiac)}</p>`;
    }
    if (data.recommendation) {
        html += `<p class="result-text" style="margin-top:8px;">${sanitizeHTML(data.recommendation)}</p>`;
    }
    if (data.favorable) {
        html += `<p class="result-text" style="margin-top:8px;"><strong style="color:var(--color-gold);">Благоприятно:</strong> ${sanitizeHTML(data.favorable)}</p>`;
    }
    if (data.unfavorable) {
        html += `<p class="result-text" style="margin-top:8px;"><strong style="color:#c4724a;">Нежелательно:</strong> ${sanitizeHTML(data.unfavorable)}</p>`;
    }
    if (data.haircut) {
        html += `<p class="result-text" style="margin-top:8px;"><strong style="color:var(--color-gold);">Стрижка:</strong> ${sanitizeHTML(data.haircut)}</p>`;
    }
    if (data.health) {
        html += `<p class="result-text" style="margin-top:8px;"><strong style="color:var(--color-gold);">Здоровье:</strong> ${sanitizeHTML(data.health)}</p>`;
    }
    if (data.ritual) {
        html += `<p class="result-text" style="margin-top:8px;"><strong style="color:var(--color-gold);">Ритуал:</strong> ${sanitizeHTML(data.ritual)}</p>`;
    }
    return html;
}

function formatNatal(data) {
    let html = '';
    if (data.message) html += `<p class="result-text">${sanitizeHTML(data.message)}</p>`;
    if (data.preliminary_analysis) html += `<p class="result-text">${sanitizeHTML(data.preliminary_analysis)}</p>`;
    if (data.ai_interpretation) html += `<p class="result-text" style="margin-top:12px;font-style:italic;">${sanitizeHTML(data.ai_interpretation)}</p>`;
    return html;
}

function formatNumerology(data) {
    let html = '';

    if (data.life_path || data.destiny) {
        html += `<div style="text-align:center;margin-bottom:20px;">
            <div style="font-size:18px;font-weight:600;color:var(--color-gold);letter-spacing:0.5px;">Твой нумерологический портрет</div>
        </div>`;

        if (data.life_path) {
            html += `
            <div style="margin-bottom:14px;padding:0;background:transparent;border:none;">
                <span style="color:var(--color-gold);font-weight:600;font-size:14px;">Число Жизненного Пути — ${data.life_path.number}</span>
                <p style="font-size:14px;color:var(--color-text);margin-top:4px;line-height:1.6;white-space:pre-line;">${sanitizeHTML(data.life_path.ai_description || data.life_path.description)}</p>
            </div>`;
        }

        if (data.destiny) {
            html += `
            <div style="margin-bottom:14px;padding:0;background:transparent;border:none;">
                <span style="color:var(--color-gold);font-weight:600;font-size:14px;">Число Судьбы — ${data.destiny.number}</span>
                <p style="font-size:14px;color:var(--color-text);margin-top:4px;line-height:1.6;white-space:pre-line;">${sanitizeHTML(data.destiny.ai_description || data.destiny.description)}</p>
            </div>`;
        }

        const extraNumbers = [
            { key: 'soul_date', emoji: '💫', name: 'Число Души (по дате)' },
            { key: 'soul_name', emoji: '💕', name: 'Число Души (по имени)' },
            { key: 'personality', emoji: '👁', name: 'Число Личности' },
            { key: 'expression', emoji: '🎯', name: 'Число Экспрессии' },
            { key: 'maturity', emoji: '🌅', name: 'Число Зрелости' },
            { key: 'karmic_debt', emoji: '🔄', name: 'Кармический долг' },
        ];

        extraNumbers.forEach(item => {
            if (data[item.key]) {
                const val = data[item.key];
                const desc = val.ai_description || val.description || '';
                html += `
                <div style="margin-bottom:14px;padding:0;background:transparent;border:none;">
                    <span style="color:var(--color-gold);font-weight:600;font-size:14px;">${item.emoji} ${item.name} — ${val.number || (val.has_debt !== undefined ? (val.has_debt ? val.number : 'нет') : '')}</span>
                    <p style="font-size:14px;color:var(--color-text);margin-top:4px;line-height:1.6;white-space:pre-line;">${sanitizeHTML(desc)}</p>
                </div>`;
            }
        });

        if (data.peaks) {
            html += `<div style="margin-top:12px;font-weight:600;color:var(--color-gold);font-size:14px;">Пики жизни</div>`;
            data.peaks.forEach(peak => {
                html += `
                <div style="margin:6px 0;padding:0;background:transparent;border:none;">
                    <span style="font-size:14px;color:var(--color-text);font-weight:600;">${sanitizeHTML(peak.age)} — пик ${peak.number}</span>
                    <p style="font-size:14px;color:var(--color-text);margin-top:2px;line-height:1.6;white-space:pre-line;">${sanitizeHTML(peak.description)}</p>
                </div>`;
            });
        }

        if (data.personal_year) {
            html += `
            <div style="margin-top:14px;padding:0;background:transparent;border:none;">
                <span style="color:var(--color-gold);font-weight:600;font-size:14px;">🌟 ${data.personal_year.year} — твой год ${data.personal_year.number}</span>
                <p style="font-size:14px;color:var(--color-text);margin-top:4px;line-height:1.6;white-space:pre-line;">${sanitizeHTML(data.personal_year.description)}</p>
            </div>`;
        }

        if (data.ai_full) {
            html += `
            <div style="margin-top:16px;padding:0;background:transparent;border:none;">
                <span style="color:var(--color-gold);font-weight:600;font-size:14px;">🌟 Итог от unanum</span>
                <p style="font-size:14px;color:var(--color-text);margin-top:6px;line-height:1.6;white-space:pre-line;overflow:visible;max-height:none;word-wrap:break-word;">${sanitizeHTML(data.ai_full)}</p>
            </div>`;
        }
    }
    return html;
}

function formatCompatibility(data) {
    let html = '';
    html += `<div class="result-code" style="font-size:42px;font-weight:700;">${data.compatibility_percent}%</div>`;
    html += `<div class="result-label">Совместимость</div>`;

    // Новый формат — карточки (если есть поля names, birth и т.д.)
    if (data.names || data.birth || data.destiny) {
        const sections = [
            { key: 'names', title: 'Совместимость по именам', subtitle: 'Как вибрации имён влияют на союз' },
            { key: 'birth', title: 'Совместимость по дате рождения', subtitle: 'Ритмы дат и их влияние' },
            { key: 'destiny', title: 'Число судьбы', subtitle: 'Кармическая задача пары' },
            { key: 'karma', title: 'Кармическая связь', subtitle: 'Уроки, которые несут друг другу' },
            { key: 'love', title: 'Любовь и эмоции', subtitle: 'Что питает и охлаждает чувства' },
            { key: 'household', title: 'Совместный быт', subtitle: 'Как живут вместе' },
            { key: 'finance', title: 'Финансовая совместимость', subtitle: 'Отношение к деньгам' },
        ];

        sections.forEach(function(sec) {
            if (data[sec.key]) {
                html += '<div style="margin-bottom:14px;padding:20px;background:rgba(30,58,30,0.4);border:1px solid var(--color-border);border-radius:16px;">';
                html += '<span style="font-size:13px;font-weight:600;color:var(--color-gold);">' + sec.title + '</span>';
                html += '<p style="font-size:12px;color:var(--color-text-lighter);margin-top:2px;margin-bottom:8px;">' + sec.subtitle + '</p>';
                html += '<p style="font-size:13px;color:var(--color-text-light);line-height:1.7;white-space:pre-line;">' + sanitizeHTML(data[sec.key]) + '</p>';
                html += '</div>';
            }
        });

        // Плюсы и Минусы
        html += '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:14px;">';
        if (data.strengths) {
            html += '<div style="flex:1;min-width:200px;padding:20px;background:rgba(30,58,30,0.4);border:1px solid #7eb89e;border-radius:16px;">';
            html += '<span style="font-size:13px;font-weight:600;color:#7eb89e;">Плюсы</span>';
            html += '<p style="font-size:13px;color:var(--color-text-light);margin-top:6px;line-height:1.7;white-space:pre-line;">' + sanitizeHTML(data.strengths) + '</p>';
            html += '</div>';
        }
        if (data.challenges) {
            html += '<div style="flex:1;min-width:200px;padding:20px;background:rgba(30,58,30,0.4);border:1px solid #d4838a;border-radius:16px;">';
            html += '<span style="font-size:13px;font-weight:600;color:#d4838a;">Минусы</span>';
            html += '<p style="font-size:13px;color:var(--color-text-light);margin-top:6px;line-height:1.7;white-space:pre-line;">' + sanitizeHTML(data.challenges) + '</p>';
            html += '</div>';
        }
        html += '</div>';

        // Совет
        if (data.advice) {
            html += '<div style="margin-bottom:14px;padding:20px;background:rgba(212,135,154,0.08);border:1px solid #d4879a;border-radius:16px;">';
            html += '<span style="font-size:13px;font-weight:600;color:#d4879a;">Совет паре</span>';
            html += '<p style="font-size:13px;color:var(--color-text-light);margin-top:6px;line-height:1.7;white-space:pre-line;">' + sanitizeHTML(data.advice) + '</p>';
            html += '</div>';
        }
        
        return html;
    }

        // Новый формат — AI-разбор объектом
    if (data.ai_interpretation && typeof data.ai_interpretation === 'object') {
        const aiSections = [
            { key: 'names', title: 'Совместимость по именам', subtitle: 'Как вибрации имён влияют на союз' },
            { key: 'birth', title: 'Совместимость по дате рождения', subtitle: 'Ритмы дат и их влияние' },
            { key: 'destiny', title: 'Число судьбы', subtitle: 'Кармическая задача пары' },
            { key: 'karma', title: 'Кармическая связь', subtitle: 'Уроки, которые несут друг другу' },
            { key: 'love', title: 'Любовь и эмоции', subtitle: 'Что питает и охлаждает чувства' },
            { key: 'household', title: 'Совместный быт', subtitle: 'Как живут вместе' },
            { key: 'finance', title: 'Финансовая совместимость', subtitle: 'Отношение к деньгам' },
        ];
        
        aiSections.forEach(function(sec) {
            if (data.ai_interpretation[sec.key]) {
                html += '<div style="margin-bottom:14px;padding:20px;background:rgba(30,58,30,0.4);border:1px solid var(--color-border);border-radius:16px;">';
                html += '<span style="font-size:13px;font-weight:600;color:var(--color-gold);">' + sec.title + '</span>';
                html += '<p style="font-size:12px;color:var(--color-text-lighter);margin-top:2px;margin-bottom:8px;">' + sec.subtitle + '</p>';
                html += '<p style="font-size:13px;color:var(--color-text-light);line-height:1.7;white-space:pre-line;">' + sanitizeHTML(data.ai_interpretation[sec.key]) + '</p>';
                html += '</div>';
            }
        });
        
        // Плюсы и Минусы
        html += '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:14px;">';
        if (data.ai_interpretation.strengths) {
            html += '<div style="flex:1;min-width:200px;padding:20px;background:rgba(30,58,30,0.4);border:1px solid #7eb89e;border-radius:16px;">';
            html += '<span style="font-size:13px;font-weight:600;color:#7eb89e;">Плюсы</span>';
            html += '<p style="font-size:13px;color:var(--color-text-light);margin-top:6px;line-height:1.7;white-space:pre-line;">' + sanitizeHTML(data.ai_interpretation.strengths) + '</p>';
            html += '</div>';
        }
        if (data.ai_interpretation.challenges) {
            html += '<div style="flex:1;min-width:200px;padding:20px;background:rgba(30,58,30,0.4);border:1px solid #d4838a;border-radius:16px;">';
            html += '<span style="font-size:13px;font-weight:600;color:#d4838a;">Минусы</span>';
            html += '<p style="font-size:13px;color:var(--color-text-light);margin-top:6px;line-height:1.7;white-space:pre-line;">' + sanitizeHTML(data.ai_interpretation.challenges) + '</p>';
            html += '</div>';
        }
        html += '</div>';
        
        if (data.ai_interpretation.advice) {
            html += '<div style="margin-bottom:14px;padding:20px;background:rgba(212,135,154,0.08);border:1px solid #d4879a;border-radius:16px;">';
            html += '<span style="font-size:13px;font-weight:600;color:#d4879a;">Совет паре</span>';
            html += '<p style="font-size:13px;color:var(--color-text-light);margin-top:6px;line-height:1.7;white-space:pre-line;">' + sanitizeHTML(data.ai_interpretation.advice) + '</p>';
            html += '</div>';
        }
        return html;
    }

    // Старый формат — бесплатный тариф (criteria_brief)
    if (data.criteria_brief && (!data.ai_interpretation || typeof data.ai_interpretation === 'object')) {
        html += '<div style="margin-top:14px;">';
        for (const [title, desc] of Object.entries(data.criteria_brief)) {
            html += `
                <div style="margin-bottom:12px;padding:0;background:transparent;border:none;">
                    <span style="color:var(--color-gold);font-weight:600;font-size:13px;">${sanitizeHTML(title)}</span>
                    <p style="font-size:13px;color:var(--color-text-light);margin:4px 0 0 0;line-height:1.7;">${sanitizeHTML(desc)}</p>
                    <p style="margin-top:2px;"><span style="color:var(--color-gold);cursor:pointer;text-decoration:underline;font-size:11px;" onclick="event.stopPropagation();showPaywall();">Читать полный разбор</span></p>
                </div>`;
        }
        html += '</div>';
    }

    // Старый формат — AI-интерпретация строкой (обратная совместимость)
    if (data.ai_interpretation && typeof data.ai_interpretation === 'string') {
        const safeName1 = sanitizeHTML(data.person1 || '');
        const safeName2 = sanitizeHTML(data.person2 || '');
        let rawText = data.ai_interpretation;
        if (data.person1) {
            const escapedPerson1 = data.person1.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            rawText = rawText.replace(new RegExp(escapedPerson1, 'g'), safeName1);
        }
        if (data.person2) {
            const escapedPerson2 = data.person2.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            rawText = rawText.replace(new RegExp(escapedPerson2, 'g'), safeName2);
        }

        const headers = [
            "Совместимость по именам",
            "Совместимость по дате рождения",
            "Число судьбы",
            "Кармическая разница",
            "Любовь",
            "Совместный быт",
            "Финансы"
        ];

        let sections = [];
        let remaining = rawText;
        let headerMatches = [];
        for (const h of headers) {
            const regex = new RegExp('(' + h.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s*\\(?(\\d+%)?\\)?)', 'gi');
            const match = regex.exec(remaining);
            if (match) {
                headerMatches.push({header: h, index: match.index, length: match[0].length});
            }
        }
        headerMatches.sort((a, b) => a.index - b.index);

        if (headerMatches.length > 0) {
            if (headerMatches[0].index > 0) {
                sections.push({header: null, content: remaining.substring(0, headerMatches[0].index)});
            }
            for (let i = 0; i < headerMatches.length; i++) {
                const current = headerMatches[i];
                const start = current.index + current.length;
                const end = (i + 1 < headerMatches.length) ? headerMatches[i + 1].index : remaining.length;
                const content = remaining.substring(start, end);
                sections.push({header: current.header, content: content});
            }
        } else {
            sections.push({header: null, content: remaining});
        }

        let safeHtml = '';
        for (const sec of sections) {
            if (sec.header) {
                safeHtml += `<br><br><span style="color:var(--color-gold);font-weight:600;">${sanitizeHTML(sec.header)}</span><br>`;
            }
            safeHtml += sanitizeHTML(sec.content).replace(/\n/g, '<br>');
        }
        safeHtml = safeHtml.replace(/^(<br>)+/, '');

        html += `<div class="result-text" style="margin-top:12px;line-height:1.8;">${safeHtml}</div>`;
    }

    if (data.conclusion) {
        html += `
        <div style="margin-top:16px;padding:14px;background:transparent;border-radius:12px;border:1px solid var(--color-gold);">
            <span style="color:var(--color-gold);font-weight:600;font-size:12px;">Итог от unanum</span>
            <p style="font-size:12px;color:var(--color-text-light);margin-top:6px;line-height:1.6;font-style:italic;">${sanitizeHTML(data.conclusion)}</p>
        </div>`;
    }

    return html;
}

// ============================================
// ПОДСКАЗКИ ВОПРОСОВ
// ============================================



// ============================================
// БИБЛИОТЕКА ТАРО
// ============================================

async function searchCards() {
    const query = document.getElementById('cardSearch')?.value || '';
    const arcana = document.getElementById('filterArcana')?.value || 'all';
    const suit = document.getElementById('filterSuit')?.value || 'all';
    const sort = document.getElementById('filterSort')?.value || 'number';
    loadLibraryCards(query, arcana, suit, sort);
}

async function loadLibraryCards(query = '', arcana = 'all', suit = 'all', sort = 'number') {
    const grid = document.getElementById('cardsGrid');
    if (!grid) return;
    grid.innerHTML = '<div class="loading-placeholder">Загрузка...</div>';

    try {
        const params = new URLSearchParams({ q: query, arcana, suit, sort });
        const res = await fetch(`/api/tarot/library?${params}`);
        const data = await res.json();

        if (data.total === 0) {
            grid.innerHTML = '<p class="empty-state">Карты не найдены.</p>';
            return;
        }

        let html = '';
        data.cards.forEach(card => {
            const suitName = { 'wands': 'Жезлы', 'cups': 'Кубки', 'swords': 'Мечи', 'pentacles': 'Пентакли' }[card.suit] || '';
            html += `
                <div class="tarot-card-mini" onclick="openCardDetail(${card.id})">
                    <div class="card-mini-inner">
                        <span class="card-mini-number">${card.number || ''}</span>
                        <h4>${sanitizeHTML(card.name_ru)}</h4>
                        <span class="card-mini-suit" style="font-size:11px;color:var(--color-text-lighter);">${sanitizeHTML(suitName)}</span>
                        <p class="card-mini-keywords">${sanitizeHTML(card.keywords.slice(0, 3).join(', '))}</p>
                    </div>
                </div>`;
        });
        grid.innerHTML = html;
    } catch (e) {
        grid.innerHTML = '<p>Не удалось загрузить карты</p>';
    }
}

function openCardDetail(cardId) {
    fetch(`/api/tarot/card/${cardId}`)
        .then(r => r.json())
        .then(card => {
            const imgFile = `${String(cardId + 2).padStart(2, '0')}.jpg`;
            const modal = document.createElement('div');
            modal.className = 'modal-overlay active';
            modal.innerHTML = `
                <div class="modal" style="max-width:300px;text-align:center;">
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">&times;</button>
                    <img src="/static/images/tarot/${imgFile}" alt="${sanitizeHTML(card.name_ru)}" style="width:100%;border-radius:14px;margin-bottom:12px;">
                    <h3>${sanitizeHTML(card.name_ru)}</h3>
                    <p style="font-size:13px;color:var(--color-text);">${sanitizeHTML(card.meaning_upright)}</p>
                    ${card.advice ? `<p style="font-size:12px;color:var(--color-gold-dark);font-style:italic;">${sanitizeHTML(card.advice)}</p>` : ''}
                </div>`;
            document.body.appendChild(modal);
            modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
        });
}

// ============================================
// PROFILE & DIARY
// ============================================


// Единый список знаков зодиака с диапазонами дат.
// name — русское имя с эмодзи (для отображения), emoji — отдельно
// (для мест, где нужен только символ, например getZodiacEmoji).
const ZODIAC_SIGNS = [
    { key: 'capricorn',   name: '♑ Козерог',   emoji: '♑', start: [1, 1],   end: [1, 19] },
    { key: 'aquarius',    name: '♒ Водолей',   emoji: '♒', start: [1, 20],  end: [2, 18] },
    { key: 'pisces',      name: '♓ Рыбы',      emoji: '♓', start: [2, 19],  end: [3, 20] },
    { key: 'aries',       name: '♈ Овен',      emoji: '♈', start: [3, 21],  end: [4, 19] },
    { key: 'taurus',      name: '♉ Телец',     emoji: '♉', start: [4, 20],  end: [5, 20] },
    { key: 'gemini',      name: '♊ Близнецы',  emoji: '♊', start: [5, 21],  end: [6, 20] },
    { key: 'cancer',      name: '♋ Рак',       emoji: '♋', start: [6, 21],  end: [7, 22] },
    { key: 'leo',         name: '♌ Лев',       emoji: '♌', start: [7, 23],  end: [8, 22] },
    { key: 'virgo',       name: '♍ Дева',      emoji: '♍', start: [8, 23],  end: [9, 22] },
    { key: 'libra',       name: '♎ Весы',      emoji: '♎', start: [9, 23],  end: [10, 22] },
    { key: 'scorpio',     name: '♏ Скорпион',  emoji: '♏', start: [10, 23], end: [11, 21] },
    { key: 'sagittarius', name: '♐ Стрелец',   emoji: '♐', start: [11, 22], end: [12, 21] },
    { key: 'capricorn',   name: '♑ Козерог',   emoji: '♑', start: [12, 22], end: [12, 31] },
];

function _findZodiac(dateStr) {
    if (!dateStr) return null;
    const parts = dateStr.split('-');
    const month = parseInt(parts[1]);
    const day = parseInt(parts[2]);
    for (const sign of ZODIAC_SIGNS) {
        if ((month === sign.start[0] && day >= sign.start[1]) ||
            (month === sign.end[0] && day <= sign.end[1])) {
            return sign;
        }
    }
    return null;
}

function getZodiacKey(dateStr) {
    const sign = _findZodiac(dateStr);
    return sign ? sign.key : null;
}

function getZodiacSign(dateStr) {
    const sign = _findZodiac(dateStr);
    return sign ? sign.name : '';
}

// ============================================
// ADMIN
// ============================================


// ============================================
// ТАРИФЫ (ПРОФИЛЬ)
// ============================================

async function selectTariff(tariffName) {
    const currentName = document.getElementById('currentTariffName')?.textContent;
    if (currentName === tariffName) {
        alert('Это твой текущий тариф ✨');
        return;
    }
    
    if (!window.isAuthenticated || window.isAuthenticated === 'false') {
        alert('Войди в аккаунт, чтобы выбрать тариф');
        return;
    }
    
    alert('🔮 Чтобы изменить тариф, напиши нам: support@unanum.ru\n\nА пока — пользуйся всеми функциями бесплатно! ✨');
}

// ============================================
// ИНИЦИАЛИЗАЦИЯ ПРОФИЛЯ
// ============================================
// (загрузка профиля — в inline-скрипте profile.html)

// ============================================
// КОНТЕКСТНЫЙ ОНБОРДИНГ НА СТРАНИЦАХ
// ============================================

function showContextOnboarding(targetSelector, message, sectionKey) {
    // Контекстные подсказки отключены
}

// ============================================
// ОНБОРДИНГ ДЛЯ ПЛАТЯЩИХ ПОЛЬЗОВАТЕЛЕЙ
// ============================================

function checkTariffUpgrade() {
    const prevTariff = localStorage.getItem('numer_prev_tariff');
    const currentTariff = window.userTariff;
    
    // Если тариф изменился в сторону повышения
    const tariffOrder = { 'Искра': 0, 'Пламя': 1 };
    if (prevTariff && tariffOrder[currentTariff] > tariffOrder[prevTariff]) {
        showTariffUpgradeModal(prevTariff, currentTariff);
    }
    
    // Всегда обновляем сохранённый тариф
    localStorage.setItem('numer_prev_tariff', currentTariff);
}

function showTariffUpgradeModal(oldTariff, newTariff) {
    const features = {
        'Пламя': [
            'Безлимитные вопросы к гороскопу',
            'Расклады Таро (3 карты)',
            'Гороскоп на год',
            'Прогноз финансового кода на 3 года',
            'Ритуалы с учётом лунного дня',
            'Совместимость финкодов с партнёром',
            'Эксклюзивные шаблоны карточек для сториз'
        ]
    };
    const tariffNames = { 'Искра': '✨ Искра', 'Пламя': '🔥 Пламя' };
    const newFeatures = features[newTariff] || [];

    const modal = document.createElement('div');
    modal.className = 'modal-overlay active';
    modal.style.zIndex = '650';
    modal.innerHTML = `
        <div class="modal" style="max-width:400px;text-align:center;">
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">&times;</button>
            <div style="font-size:48px;margin-bottom:8px;animation: bounceIn 0.6s ease;">✨</div>
            <h2 style="font-size:20px;color:var(--color-gold);margin-bottom:4px;">Твой путь расширяется</h2>
            <p style="font-size:14px;color:var(--color-text-light);margin-bottom:16px;">
                Ты перешла с тарифа ${tariffNames[oldTariff] || oldTariff} на ${tariffNames[newTariff] || newTariff}
            </p>
            <div style="text-align:left;margin-bottom:16px;">
                <p style="font-size:13px;color:var(--color-text-light);margin-bottom:8px;font-weight:600;">Что тебе открылось:</p>
                ${newFeatures.map(f => 
                    `<div style="display:flex;align-items:center;gap:8px;padding:6px 0;font-size:13px;color:var(--color-text);">
                        <span style="color:var(--color-gold);">✦</span> ${f}
                    </div>`
                ).join('')}
            </div>
            <button class="btn btn-primary" onclick="this.closest('.modal-overlay').remove();" style="width:100%;">
                Исследовать
            </button>
        </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
}

// ============================================
// ЕЖЕДНЕВНЫЙ ОПРОС (DAILY INSIGHT)
// ============================================

let dailyQuestions = [];
let currentQuestionIndex = 0;
let userAnswers = [];

async function checkDailyInsight() {
    if (window.location.pathname === '/moon-calendar') return;
    
    // Загружаем теги пользователя при первой проверке
    if (window.isAuthenticated && window.isAuthenticated !== 'false') {
        try {
            const profileRes = await fetch('/api/user-profile');
            const profile = await profileRes.json();
            if (profile.tag_counts) {
                window.userTags = Object.keys(profile.tag_counts).sort(
                    (a, b) => (profile.tag_counts[b] || 0) - (profile.tag_counts[a] || 0)
                );
            }
        } catch(e) {
        }
    }
    
    try {
        const res = await fetch('/api/daily-insights/today');
        const data = await res.json();
        if (data.completed) return;
    } catch(e) {}
    loadDailyQuestions();
}

async function loadDailyQuestions() {
    try {
        const res = await fetch('/api/daily-questions');
        const data = await res.json();
        dailyQuestions = data.questions;
        currentQuestionIndex = 0;
        userAnswers = [];
        showInsightModal();
        renderQuestion();
    } catch(e) {
    }
}

function showInsightModal() {
    document.getElementById('insightModal').classList.add('active');
}

function closeInsightModal(skipped = false) {
    document.getElementById('insightModal').classList.remove('active');
    if (skipped && userAnswers.length === 0) {
        showSkipWarning();
        saveInsight([{text: 'Пропущено', tags: ['sad']}]);
    }
}

function showSkipWarning() {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay active';
    modal.style.zIndex = '600';
    modal.innerHTML = `
        <div class="modal" style="max-width:320px;text-align:center;">
            <p style="font-size:16px;color:var(--color-text);">Это помогает делать ответы точнее</p>
            <p style="font-size:12px;color:var(--color-text-lighter);margin:12px 0;">Завтра будут новые вопросы</p>
            <button class="btn btn-primary btn-sm" onclick="this.closest('.modal-overlay').remove()">Понятно</button>
        </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
}

function renderQuestion() {
    const container = document.getElementById('insightContent');
    if (currentQuestionIndex >= dailyQuestions.length) {
        finishInsight();
        return;
    }
    const q = dailyQuestions[currentQuestionIndex];
    
    let btnsHtml = '';
    q.answers.forEach((a) => {
        btnsHtml += `<button class="btn btn-outline btn-sm insight-answer-btn" style="text-align:left;white-space:normal;">${a.text}</button>`;
    });
    
    container.innerHTML = `
        <h3 style="color:var(--color-text);margin-bottom:4px;">${q.question}</h3>
        <div class="insight-answers" style="display:flex;flex-direction:column;gap:8px;margin-top:16px;">
            ${btnsHtml}
        </div>
        <p style="font-size:11px;color:var(--color-text-lighter);margin-top:12px;">Вопрос ${currentQuestionIndex+1} из ${dailyQuestions.length}</p>
    `;
    
    // Вешаем обработчики
    const buttons = container.querySelectorAll('.insight-answer-btn');
    buttons.forEach((btn, index) => {
        btn.addEventListener('click', function() {
            const answer = q.answers[index];
            selectAnswer(answer.text, answer.tags);
        });
    });
}

function selectAnswer(text, tags) {
    userAnswers.push({text, tags});
    currentQuestionIndex++;
    renderQuestion();
}

function finishInsight() {
    document.getElementById('insightContent').innerHTML = `
        <div style="font-size:40px;margin-bottom:12px;">✨</div>
        <h3 style="color:var(--color-text);">Принято!</h3>
        <p style="font-size:14px;color:var(--color-text-light);">Ваш компас настроен на сегодня</p>
    `;
    setTimeout(() => closeInsightModal(false), 1500);
    saveInsight(userAnswers);
}

async function saveInsight(answers) {
    try {
        const res = await fetch('/api/daily-insights', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({answers})
        });
        const data = await res.json();
        if (data.tags) {
            window.userTags = data.tags;
        }
    } catch(e) {
        // тихо игнорируем — пользователь не должен видеть технические ошибки
    }
}

// ============================================
// unanum DIALOG
// ============================================

let numerQuestions = [];

function openNumerDialog() {
    var modal = document.getElementById('numerModal');
    var content = document.getElementById('numerContent');
    var answers = document.getElementById('numerAnswers');
    
    modal.classList.add('active');
    answers.innerHTML = '';
    
    fetch('/api/numer/portrait')
        .then(function(r) { return r.json(); })
        .then(function(portrait) {
            if (portrait.name) {
                content.innerHTML = '<p style="text-align:center;color:var(--color-gold);font-weight:500;">Unanum слушает</p>';
            } else {
                content.innerHTML = '<div style="text-align:center;"><img src="/static/icon/unanum_logo.svg" alt="Unanum" style="height:24px;width:auto;margin-bottom:8px;"><p style="color:var(--color-gold);font-weight:500;margin-top:0;">Спроси о чём хочешь</p></div>';
            }
        });
    
    loadNumerQuestions('general');
}

function closeNumerDialog() {
    document.getElementById('numerModal').classList.remove('active');
}

async function loadNumerQuestions(section) {
    var container1 = document.getElementById('numerMarqueeRow1');
    var container2 = document.getElementById('numerMarqueeRow2');
    var container3 = document.getElementById('numerMarqueeRow3');
    if (!container1) return;
    
    // Сначала показываем кэшированные или fallback-вопросы
    var cacheKey = 'numer_marquee_' + new Date().toISOString().split('T')[0];
    var cached = sessionStorage.getItem(cacheKey);
    
    if (cached) {
        renderMarquee(JSON.parse(cached));
        return;
    }
    
    // Показываем fallback сразу
    var fallback = [
        "Почему гороскопы врут?",
        "Что если всё предопределено?",
        "Как привлечь деньги уже сегодня?",
        "А если партнёр не тот?",
        "Когда лучше начинать новое?",
        "Какой день недели ваш?",
        "Что делать когда всё бесит?",
        "Как вернуть себе спокойствие?",
        "Кто сказал что это нельзя?",
        "Почему удача обходит стороной?",
        "Что скрывает дата рождения?",
        "А если судьбу можно выбрать?",
        "Как понять что карта не врёт?",
        "Почему именно эта цифра?",
        "Что Луна советует прямо сейчас?",
    ];
    renderMarquee(fallback);
    
    // Затем в фоне пытаемся загрузить AI-вопросы
    try {
        var res = await fetch('/api/numer/dialogue', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                message: 'придумай 12 коротких интригующих вопросов для бегущей строки',
                section: 'marquee_questions'
            })
        });
        var data = await res.json();
        
        if (data.answer) {
            var questions = data.answer.split('\n').filter(function(line) {
                return line.trim().length > 0;
            }).map(function(line) {
                return line.replace(/^[\d\.\-\*\s]+/, '').trim();
            }).filter(function(q) {
                return q.length >= 10 && q.length <= 80;
            });
            
            if (questions.length >= 6) {
                sessionStorage.setItem(cacheKey, JSON.stringify(questions));
                renderMarquee(questions);
            }
        }
    } catch(e) {
        // Оставляем fallback
    }
}

function renderMarquee(questions) {
    // Перемешиваем
    var shuffled = questions.sort(function() { return Math.random() - 0.5; });
    
    // Делим на три ряда
    var row1 = shuffled.slice(0, Math.ceil(shuffled.length / 3));
    var row2 = shuffled.slice(row1.length, row1.length * 2);
    var row3 = shuffled.slice(row1.length * 2);
    
    function renderRow(container, items) {
        var doubled = items.concat(items).concat(items); // троим для бесшовной анимации
        container.innerHTML = doubled.map(function(q) {
            // data-question — безопасный атрибут, не inline-JS
            var attrQ = String(q).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
            return '<span class="numer-marquee-item" data-question="' + attrQ + '">' + sanitizeHTML(q) + '</span>';
        }).join('');
    }
    
    renderRow(document.getElementById('numerMarqueeRow1'), row1);
    renderRow(document.getElementById('numerMarqueeRow2'), row2);
    renderRow(document.getElementById('numerMarqueeRow3'), row3);
    
    // Делегированный обработчик — вешается один раз
    var marquee = document.getElementById('numerMarquee');
    if (marquee && !marquee.dataset.marqueeBound) {
        marquee.dataset.marqueeBound = '1';
        marquee.addEventListener('click', function(e) {
            var item = e.target.closest('.numer-marquee-item');
            if (item && item.dataset.question) {
                askNumerQuestion(item.dataset.question);
            }
        });
    }
}

function askNumerQuestion(question) {
    var input = document.getElementById('numerInput');
    if (input) {
        input.value = question;
        input.style.height = 'auto';
        input.style.height = input.scrollHeight + 'px';
        updateNumerButton();
    }
}

async function sendNumerMessage() {
    var input = document.getElementById('numerInput');
    var message = input.value.trim();
    if (!message) return;
    
    var answers = document.getElementById('numerAnswers');
    
    // Проверка лимита — как раньше. Отдельный запрос к /api/numer/check-limit.
    // Не трогаем: это защита от лишних обращений к DeepSeek.
    try {
        var limitRes = await fetch('/api/numer/check-limit');
        var limitData = await limitRes.json();
        if (!limitData.can_ask) {
            var limitMsg = document.createElement('div');
            limitMsg.style.cssText = 'display:flex;justify-content:center;margin-bottom:8px;';
            limitMsg.innerHTML = '<div style="background:rgba(212,131,138,0.15);border:1px solid #d4838a;border-radius:12px;padding:12px 16px;max-width:90%;text-align:center;"><p style="font-size:13px;color:#d4838a;margin:0;">Лимит вопросов на сегодня исчерпан (' + limitData.limit + ' в день)</p><p style="font-size:11px;color:var(--color-text-lighter);margin:6px 0 0 0;">На тарифе Пламя — безлимит</p><button class="btn btn-share btn-sm" onclick="closeNumerDialog();showPaywall();" style="margin-top:8px;">Открыть безлимит — ' + (window.paywallPrice || 599) + ' ₽</button></div>';
            answers.appendChild(limitMsg);
            answers.scrollTop = answers.scrollHeight;
            input.value = '';
            updateNumerButton();
            return;
        }
    } catch(e) {}
    
    // Пузырь ответа — тот же самый визуально, что был.
    // Первое содержимое — «Печатает...». Затем наполняется чанками.
    // Стили идентичны старой версии, чтобы не менять UX.
    var answerWrap = document.createElement('div');
    answerWrap.style.cssText = 'display:flex;justify-content:flex-start;margin-bottom:4px;';
    var bubble = document.createElement('div');
    bubble.style.cssText = 'background:rgba(30,58,30,0.6);border-radius:18px 18px 18px 4px;padding:10px 16px;max-width:90%;font-size:14px;color:var(--color-text-light);line-height:1.5;word-wrap:break-word;';
    bubble.textContent = 'Печатает...';
    answerWrap.appendChild(bubble);
    answers.appendChild(answerWrap);
    answers.scrollTop = answers.scrollHeight;
    
    input.value = '';
    updateNumerButton();
    
    // Стрим через универсальный streamPost (static/js/stream-client.js).
    // onChunk наполняет bubble.textContent — это безопасно (не innerHTML),
    // XSS исключён без sanitizeHTML. Новые строки не рендерятся как <br> —
    // поведение совпадает со старой версией (там был sanitizeHTML → innerHTML,
    // \n тоже не превращались в переносы).
    var firstChunk = true;
    
    await streamPost(
        '/api/numer/dialogue/stream',
        { message: message, section: 'general' },
        {
            onMeta: function(meta) {
                // Метаданные приходят за ~300 мс до первого чанка.
                // Можно было бы показать здесь, но текущий UI этого не требует.
                // Оставлено на будущее: убрать «Печатает...» и показать индикатор раздела.
            },
            onChunk: function(data) {
                // stream-client теперь передаёт полный объект {chunk, [name], ...}.
                // Для чата name не используется — только текст.
                const chunk = data.chunk || '';
                if (firstChunk) {
                    bubble.textContent = '';   // убрать «Печатает...»
                    firstChunk = false;
                }
                bubble.textContent += chunk;
                answers.scrollTop = answers.scrollHeight;
            },
            onError: function(err) {
                // Ошибка в стриме или HTTP-ошибка — показываем в том же пузыре.
                // Раньше пузырь просто удалялся — пользователь не видел причину.
                bubble.textContent = err.message || 'Что-то пошло не так. Попробуй ещё раз.';
                bubble.style.color = '#d4838a';
            },
            onDone: function(data) {
                // Всё уже накоплено в bubble.textContent.
                // data.full_text совпадает с ним — можно было бы заменить,
                // но это лишний DOM-реflow в конце ответа.
            },
        }
    );
    
    // Вопрос пользователя — под ответом, справа.
    // Порядок сообщений сохранён как в старой версии (ответ → вопрос).
    var userMsg = document.createElement('div');
    userMsg.style.cssText = 'display:flex;justify-content:flex-end;margin-bottom:8px;';
    userMsg.innerHTML = '<div style="background:rgba(76,175,80,0.35);border-radius:18px 18px 4px 18px;padding:10px 16px;max-width:90%;font-size:14px;color:var(--color-text);line-height:1.5;word-wrap:break-word;">' + sanitizeHTML(message) + '</div>';
    answers.appendChild(userMsg);
    answers.scrollTop = answers.scrollHeight;
}

function updateNumerButton() {
    var input = document.getElementById('numerInput');
    var btn = document.getElementById('numerSendBtn');
    if (!input || !btn) return;
    
    if (input.value.trim()) {
        btn.disabled = false;
        btn.style.background = 'linear-gradient(135deg, #d4a843, #d4879a)';
        btn.style.cursor = 'pointer';
        btn.style.opacity = '1';
    } else {
        btn.disabled = true;
        btn.style.background = 'var(--color-border)';
        btn.style.cursor = 'default';
        btn.style.opacity = '0.5';
    }
}

// Закрытие по Escape
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeNumerDialog();
        closeDailyCardModal();
    }
});

// Закрытие по клику вне модалки (после загрузки DOM)
document.addEventListener('DOMContentLoaded', function() {
    const numerModal = document.getElementById('numerModal');
    if (numerModal) {
        numerModal.addEventListener('click', function(e) {
            if (e.target === this) closeNumerDialog();
        });
    }
});

// ============================================
// ОБЩИЙ ЛИМИТ ВОПРОСОВ
// Гость: 1/сутки, Искра: 3/сутки, Пламя: безлимит
// ============================================
const QUESTION_LIMIT_KEY = 'numer_question_timestamps';

function _getQuestionLimit() {
    if (window.userTariff === 'Пламя') return Infinity;
    if (window.isAuthenticated && window.isAuthenticated !== 'false') return 3;
    return 1;
}

function _getFreshStamps() {
    let stamps = [];
    try {
        stamps = JSON.parse(localStorage.getItem(QUESTION_LIMIT_KEY) || '[]');
    } catch (e) { stamps = []; }
    const dayAgo = Date.now() - 24 * 60 * 60 * 1000;
    return stamps.filter(ts => typeof ts === 'number' && ts > dayAgo);
}

function canAskQuestion() {
    const limit = _getQuestionLimit();
    if (limit === Infinity) return true;
    return _getFreshStamps().length < limit;
}

function markQuestionAsked() {
    const stamps = _getFreshStamps();
    stamps.push(Date.now());
    localStorage.setItem(QUESTION_LIMIT_KEY, JSON.stringify(stamps));
}

function updateQuestionLimitText(elementId) {
    const limitEl = document.getElementById(elementId);
    if (!limitEl) return;
    const limit = _getQuestionLimit();
    if (limit === Infinity) {
        limitEl.textContent = '';
        return;
    }
    const used = _getFreshStamps().length;
    const remaining = Math.max(0, limit - used);
    if (remaining > 0) {
        limitEl.textContent = `Осталось вопросов: ${remaining} из ${limit}.`;
    } else {
        limitEl.textContent = `Лимит вопросов исчерпан (${limit} в день). На тарифе Пламя — безлимит.`;
    }
}

function showPaywall() {
    document.getElementById('paywallModal').classList.add('active');
}
function closePaywall() {
    document.getElementById('paywallModal').classList.remove('active');
}

// ============================================
// ПОСВЯЩЕНИЕ (ОНБОРДИНГ)
// ============================================

let initData = {
    name: '',
    birth_date: '',
    birth_time: '12:00',
    birth_place: '',
    life_themes: [],
    tone: '',
    coping: ''
};

function checkInit() {
    const initModal = document.getElementById('initModal');
    
    if (window.isAuthenticated && window.isAuthenticated !== 'false') {
        // Онбординг только при первом входе после регистрации
        if (sessionStorage.getItem('show_onboarding') === 'true') {
            sessionStorage.removeItem('show_onboarding');
            fetch('/api/numer/portrait')
                .then(r => r.json())
                .then(portrait => {
                    if (!portrait.life_themes || portrait.life_themes.length === 0 ||
                        !portrait.tone || !portrait.coping) {
                        showOnboardingForAuth(portrait);
                    }
                });
        }
        return;
    }
    
    // Для гостей — проверяем localStorage с учётом даты
    const initDoneDate = localStorage.getItem('numer_init_done_date');
    const today = new Date().toDateString();
    if (initDoneDate === today) {
        // Уже проходили сегодня — загружаем сохранённые данные
        const savedData = localStorage.getItem('guest_init_data');
        if (savedData) {
            try {
                const data = JSON.parse(savedData);
                initData = data;
            } catch(e) {}
        }
        return;
    }
    
    // Проверяем портрет на сервере
    fetch('/api/numer/portrait')
        .then(r => r.json())
        .then(portrait => {
            if (!portrait.name || !portrait.birth_date) {
                // Показываем сразу (с минимальной задержкой для рендеринга)
                setTimeout(() => {
                    initModal.classList.add('active');
                }, 300);
            } else {
                // Портрет есть — запоминаем
                localStorage.setItem('numer_init_done', 'true');
            }
        });
}

function showOnboardingForAuth(portrait) {
    // Сначала получаем актуальные данные профиля, чтобы гарантированно заполнить имя и дату
    fetch('/api/profile/data')
        .then(r => r.json())
        .then(profile => {
            // Заполняем initData из профиля, если портрет не содержит
            initData.name = portrait.name || profile.name || '';
            initData.birth_date = portrait.birth_date || profile.birth_date || '';
            initData.birth_time = portrait.birth_time || '12:00';
            initData.birth_place = portrait.birth_place || '';

            // Показываем шаг 2
            document.getElementById('initStep1').style.display = 'none';
            document.getElementById('initStep2').style.display = 'block';
            
            // Предвыбор тем, если есть
            if (portrait.life_themes && portrait.life_themes.length > 0) {
                const themes = portrait.life_themes;
                document.getElementById('initThemes').querySelectorAll('.init-theme').forEach(el => {
                    if (themes.includes(el.dataset.theme)) el.classList.add('selected');
                });
            }
            
            document.getElementById('initModal').classList.add('active');
        });
}


function goInitStep2() {
    initData.name = document.getElementById('initName').value;
    initData.birth_date = document.getElementById('initBirthDate').value;
    initData.birth_time = document.getElementById('initBirthTime').value;
    initData.birth_place = document.getElementById('initBirthPlace').value;
    
    document.getElementById('initStep1').style.display = 'none';
    document.getElementById('initStep2').style.display = 'block';
}

function toggleInitTheme(el) {
    el.classList.toggle('selected');
}

function selectInitOption(el, groupId) {
    const group = document.getElementById(groupId);
    group.querySelectorAll('.init-theme').forEach(t => t.classList.remove('selected'));
    el.classList.add('selected');
}

function goInitStep3() {
    // Собираем выбранные темы
    const themes = document.getElementById('initThemes').querySelectorAll('.selected');
    initData.life_themes = Array.from(themes).map(t => t.dataset.theme);
    
    document.getElementById('initStep2').style.display = 'none';
    localStorage.setItem('numer_init_done', 'true');
    document.getElementById('initStep3').style.display = 'block';
}



function finishInit() {
    // Собираем тон
    const toneEl = document.getElementById('initTones').querySelector('.selected');
    initData.tone = toneEl ? toneEl.dataset.value : '';
    
    // Собираем coping
    const copingEl = document.getElementById('initCoping').querySelector('.selected');
    initData.coping = copingEl ? copingEl.dataset.value : '';
    
    // Отправляем на сервер
    showLoading();
    fetch('/api/numer/init', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(initData)
    })
    .then(r => r.json())
    .then(data => {
        hideLoading();
        // Сохраняем данные гостя в localStorage
        if (!window.isAuthenticated || window.isAuthenticated === 'false') {
            localStorage.setItem('guest_init_data', JSON.stringify(initData));
            localStorage.setItem('numer_init_done_date', new Date().toDateString());
        }
        if (data.success) {
            document.getElementById('initStep3').style.display = 'none';
            document.getElementById('initStep4').style.display = 'block';
            document.getElementById('initGreeting').textContent = data.greeting;
            
            // Меняем контент финального шага: добавляем две кнопки
            const step4 = document.getElementById('initStep4');
            const greeting = document.getElementById('initGreeting');
            // Находим кнопку "Открыть Unanum" и заменяем её блоком с выбором
            const oldBtn = step4.querySelector('button');
            if (oldBtn) {
                const btnContainer = document.createElement('div');
                btnContainer.style.cssText = 'margin-top:16px;';
                btnContainer.innerHTML = `
                    <button class="btn btn-primary" onclick="closeInit()" style="width:100%;">Понятно</button>
                `;
                oldBtn.replaceWith(btnContainer);
            }
        }
    })
    .catch(() => {
        hideLoading();
        closeInit();
    });
}

function closeInit() {
    document.getElementById('initModal').classList.remove('active');
}

function skipInit() {
    localStorage.setItem('numer_init_done', 'true');
    localStorage.setItem('numer_init_done_date', new Date().toDateString());
    document.getElementById('initModal').classList.remove('active');
}


// Запускаем проверку посвящения при загрузке
document.addEventListener('DOMContentLoaded', function() {
    // ОТКЛЮЧЕНО (2026-11-18): окна "Давай познакомимся" и "Что тебя сейчас волнует?"
    // временно не показываем. Вернуть — раскомментировать строку ниже.
    // setTimeout(checkInit, 2000);
});