function getDayHint(dayData) {
    const lunarDay = dayData.lunar_day;
    const hints = {
        1: 'День новых планов', 2: 'Время обучения', 3: 'Активные дела', 4: 'Укреплять связи',
        5: 'Творческий день', 6: 'Слушать интуицию', 7: 'Сила слова', 8: 'Преодолеть страх',
        9: 'День осторожности', 10: 'Семья и дом', 11: 'Энергия на пике', 12: 'Любовь и мудрость',
        13: 'Магия и ритуалы', 14: 'Завершить дела', 15: 'Полнолуние', 16: 'Очищение души',
        17: 'Радость и праздник', 18: 'Осознать уроки', 19: 'День отдыха', 20: 'Новые знания',
        21: 'Движение вперёд', 22: 'Делиться опытом', 23: 'Очистить пространство', 24: 'Ближе к природе',
        25: 'Замедлиться', 26: 'Общение', 27: 'Водные процедуры', 28: 'Красота и уход',
        29: 'Простить и отпустить', 30: 'Благодарность'
    };
    return hints[lunarDay] || '';
}

function getUserTimezone() {
    try { return Intl.DateTimeFormat().resolvedOptions().timeZone; }
    catch(e) { return 'Europe/Moscow'; }
}

const MONTH_NAMES = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
const MONTH_NAMES_SHORT = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'];

let currentYear = new Date().getFullYear();
let currentMonth = new Date().getMonth();
let today = new Date();
let monthData = null;

function initMoonCalendar() {
    updateNavigation();
    loadMonthData();
}

function updateNavigation() {
    document.getElementById('prevYear').textContent = currentYear - 1;
    document.getElementById('currentYearDisplay').textContent = currentYear;
    document.getElementById('nextYear').textContent = currentYear + 1;
    document.getElementById('monthYearTitle').textContent = MONTH_NAMES[currentMonth] + ' ' + currentYear;
    
    const scroll = document.getElementById('monthsScroll');
    let html = '';
    for (let i = currentMonth - 2; i <= currentMonth + 2; i++) {
        let monthIndex = i;
        if (monthIndex < 0) monthIndex += 12;
        if (monthIndex > 11) monthIndex -= 12;
        const isActive = monthIndex === currentMonth;
        html += `<button class="month-btn${isActive ? ' active' : ''}" onclick="selectMonth(${monthIndex})">${MONTH_NAMES_SHORT[monthIndex]}</button>`;
    }
    scroll.innerHTML = html;
}

function changeYear(delta) { currentYear += delta; updateNavigation(); loadMonthData(); }
function changeMonth(delta) {
    currentMonth += delta;
    if (currentMonth < 0) { currentMonth = 11; currentYear--; }
    else if (currentMonth > 11) { currentMonth = 0; currentYear++; }
    updateNavigation(); loadMonthData();
}
function selectMonth(month) { currentMonth = month; updateNavigation(); loadMonthData(); }

async function loadMonthData() {
    document.getElementById('moonLoading').style.display = 'block';
    document.getElementById('moonCalendarGrid').style.display = 'none';
    document.getElementById('dayDetail').style.display = 'none';
    
    let mood = null;
    if (window.isAuthenticated && window.isAuthenticated !== 'false') {
        try {
            const profileRes = await fetch('/api/user-profile');
            const profile = await profileRes.json();
            mood = profile.dominant_tag || null;
        } catch(e) {}
    }
    
    try {
        const res = await fetch('/api/moon-calendar/month', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ year: currentYear, month: currentMonth + 1, timezone: getUserTimezone(), mood: mood })
        });
        const data = await res.json();
        document.getElementById('moonLoading').style.display = 'none';
        
        if (data.error) {
            document.getElementById('moonCalendarGrid').style.display = 'block';
            document.getElementById('calendarCells').innerHTML = `<p style="grid-column:1/-1;text-align:center;color:var(--color-error);">${data.error}</p>`;
            return;
        }
        
        monthData = data;
        renderCalendar(data);
        
        if (data.mood_greeting) {
            const greetingEl = document.getElementById('moodGreeting');
            if (greetingEl) {
                greetingEl.textContent = data.mood_greeting + ' ✨';
                greetingEl.style.display = 'block';
            }
        }
        
        document.getElementById('moonCalendarGrid').style.display = 'block';
        
        if (typeof showContextOnboarding === 'function') {
            showContextOnboarding('#moonCalendarGrid',
                'Нажми на любой день, чтобы увидеть лунные рекомендации, ритуалы и советы по стрижкам.',
                'moon_calendar');
        }
    } catch (e) {
        document.getElementById('moonLoading').style.display = 'none';
        document.getElementById('moonCalendarGrid').style.display = 'block';
        document.getElementById('calendarCells').innerHTML = '<p style="grid-column:1/-1;text-align:center;color:var(--color-error);">Не удалось загрузить данные</p>';
    }
}

function renderCalendar(data) {
    const cells = document.getElementById('calendarCells');
    const daysInMonth = data.days_in_month;
    const firstDayOfWeek = data.first_day_of_week;
    const days = data.days;
    
    let html = '';
    for (let i = 0; i < firstDayOfWeek; i++) {
        html += '<div class="calendar-cell empty"></div>';
    }
    
    for (let i = 0; i < daysInMonth; i++) {
        const dayData = days[i];
        const dayNum = i + 1;
        const isToday = (currentYear === today.getFullYear() && currentMonth === today.getMonth() && dayNum === today.getDate());
        const isHighlighted = data.highlighted_days && data.highlighted_days.includes(dayData.lunar_day);
        const hint = getDayHint(dayData);
        const phaseEmoji = getPhaseEmoji(dayData.phase_name);
        html += `
            <div class="calendar-cell${isToday ? ' today' : ''}${isHighlighted ? ' mood-highlight' : ''}" onclick="showDayDetail(${dayNum})">
                <div class="day-number">${dayNum}</div>
                <div class="phase-icon" style="font-size: 24px;">${phaseEmoji}</div>
                <div class="lunar-day-num">${dayData.lunar_day} л.д.</div>
                <div class="day-hint">${hint}</div>
            </div>`;
    }
    
    cells.innerHTML = html;
}

// ============================================
// ОТРИСОВКА ДЕТАЛКИ ДНЯ
// ============================================

function showDayDetail(dayNum) {
    if (!monthData || !monthData.days[dayNum - 1]) return;
    const dayData = monthData.days[dayNum - 1];
    const isPremium = window.userTariff === 'Пламя';
    const detail = document.getElementById('dayDetail');
    detail.style.display = 'block';

    if (isPremium) {
        showDayDetailStream(dayNum, dayData, detail);
        return;
    }

    renderMoonDetail(dayData, null, false);
}

async function showDayDetailStream(dayNum, dayData, detail) {
    // Показываем заглушку загрузки.
    detail.innerHTML = `<div style="max-width:400px;margin:0 auto;text-align:center;padding:40px;">
        <div style="display:inline-block;width:36px;height:36px;border:3px solid var(--color-border);border-top-color:var(--color-gold);border-radius:50%;animation:spin 1s linear infinite;"></div>
        <p style="color:var(--color-text-light);margin-top:12px;">Создаём персональный путеводитель...</p>
    </div>`;
    detail.scrollIntoView({ behavior: 'smooth', block: 'center' });

    // Собираем aiData из блоков; в onDone передаём в renderMoonDetail —
    // она получает объект ровно той структуры, что раньше приходил из fetch.
    const aiData = {};

    await streamPost(
        '/api/moon-calendar/ai-full/stream',
        {
            lunar_day: dayData.lunar_day,
            phase_name: dayData.phase_name,
            moon_zodiac: dayData.moon_zodiac,
            illumination: dayData.illumination || 0,
        },
        {
            onMeta: function(_meta) {
                // Ничего не делаем — лоадер уже показан.
            },
            onBlock: function(b) {
                if (b.name && b.value) aiData[b.name] = b.value;
            },
            onError: function() {
                // При ошибке отдаём базовый (не-AI) рендер — как раньше.
                renderMoonDetail(dayData, null, true);
            },
            onDone: function() {
                // Тот же вызов, что был в .then(aiData => renderMoonDetail(dayData, aiData, true)).
                renderMoonDetail(dayData, aiData, true);
            },
        }
    );
}

function renderMoonDetail(dayData, aiData, isPremium) {
    const dateStr = `${dayData.day} ${MONTH_NAMES[currentMonth].toLowerCase()} ${currentYear}`;
    const detail = document.getElementById('dayDetail');
    detail.style.display = 'block';

    const recommendation = aiData ? aiData.recommendation : (isPremium ? (dayData.recommendation || 'Доверьтесь ритмам Вселенной.') : (dayData.recommendation || 'Доверьтесь ритмам Вселенной.').split('. ').slice(0, 2).join('. ') + '.');
    const favorable = (aiData && aiData.favorable) || (dayData.favorable || '');
    const unfavorable = (aiData && aiData.unfavorable) || (dayData.unfavorable || '');
    const haircut = (aiData && aiData.haircut) || (dayData.haircut || '');
    const health = (aiData && aiData.health) || (dayData.health || '');
    const ritual = aiData ? aiData.ritual : (dayData.ritual || '');

    detail.innerHTML = `
        <div style="max-width:400px;margin:0 auto;">
            <div style="text-align:center;padding:0;margin-bottom:16px;background:transparent;border:none;">
                <div style="font-size:clamp(2rem, 5vw, 2.5rem);font-weight:700;background:linear-gradient(135deg, #d4a843, #d4879a);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">${dayData.phase_name}</div>
                <div style="font-size:13px;color:var(--color-text-lighter);margin-top:4px;">${dayData.lunar_day}-й лунный день</div>
                ${!isPremium ? '<div style="font-size:11px;color:var(--color-gold);margin-top:6px;">Освещённость: ' + (dayData.illumination || '?') + '%</div>' : ''}
            </div>
            <div style="margin-bottom:10px;">
                <span style="color:var(--color-gold);font-weight:600;font-size:12px;">Дата</span>
                <p style="font-size:13px;color:var(--color-text);">${dateStr}</p>
            </div>
            <div style="margin-bottom:10px;">
                <span style="color:var(--color-gold);font-weight:600;font-size:12px;">${getZodiacEmoji(dayData.moon_zodiac)} Знак Луны — ${dayData.moon_zodiac || '—'}</span>
                ${isPremium && dayData.moonrise ? `<p style="font-size:11px;color:var(--color-text-lighter);margin-top:2px;">Восход: ${dayData.moonrise} · Заход: ${dayData.moonset}</p>` : ''}
            </div>
            <div style="margin-bottom:16px;padding:0;background:transparent;border:none;">
                <span style="color:var(--color-gold);font-weight:600;font-size:12px;">Рекомендация дня</span>
                <p style="font-size:12px;color:var(--color-text-light);margin-top:4px;line-height:1.6;">${recommendation}</p>
                ${!isPremium ? '<p style="font-size:10px;color:var(--color-gold);margin-top:4px;cursor:pointer;font-style:italic;" onclick="showPaywall()">А что если этот день приготовил нечто большее?</p>' : ''}
                <div style="margin-top:8px;display:flex;gap:16px;font-size:11px;">
                    <div style="flex:1;padding:10px;background:linear-gradient(135deg, rgba(255,213,79,0.05), rgba(30,58,30,0.3));border-radius:12px;border:1px solid var(--color-gold);">
                        <span style="color:var(--color-gold);font-weight:600;">Благоприятно</span>
                        <p style="color:var(--color-text);margin-top:2px;">${favorable}</p>
                    </div>
                    <div style="flex:1;padding:10px;background:linear-gradient(135deg, rgba(255,213,79,0.05), rgba(30,58,30,0.3));border-radius:12px;border:1px solid var(--color-gold);">
                        <span style="color:#c4724a;font-weight:600;">Нежелательно</span>
                        <p style="color:var(--color-text);margin-top:2px;">${unfavorable}</p>
                    </div>
                </div>
            </div>
            <div style="margin-bottom:16px;padding:0;background:transparent;border:none;">
                <span style="color:var(--color-gold);font-weight:600;font-size:12px;">Стрижка и красота</span>
                <p style="font-size:12px;color:var(--color-text-light);margin-top:2px;line-height:1.6;">${haircut}</p>
                ${!isPremium ? '<p style="font-size:10px;color:var(--color-gold);margin-top:4px;cursor:pointer;font-style:italic;" onclick="showPaywall()">Один нюанс меняет всю картину...</p>' : ''}
            </div>
            <div style="margin-bottom:16px;padding:0;background:transparent;border:none;">
                <span style="color:var(--color-gold);font-weight:600;font-size:12px;">Здоровье и процедуры</span>
                <p style="font-size:12px;color:var(--color-text-light);margin-top:2px;line-height:1.6;">${health}</p>
                ${!isPremium ? '<p style="font-size:10px;color:var(--color-gold);margin-top:4px;cursor:pointer;font-style:italic;" onclick="showPaywall()">Что скрывает этот лунный день для здоровья?</p>' : ''}
            </div>
            ${ritual ? `
            <div style="margin-bottom:16px;padding:0;background:transparent;border:none;">
                <span style="color:var(--color-gold);font-weight:600;font-size:12px;">Ритуал дня</span>
                <p style="font-size:12px;color:var(--color-text-light);margin-top:2px;line-height:1.6;">${ritual}</p>
                ${!isPremium ? '<p style="font-size:10px;color:var(--color-gold);margin-top:4px;cursor:pointer;font-style:italic;" onclick="showPaywall()">Один ритуал способен изменить ход дня...</p>' : ''}
            </div>` : ''}
            ${isPremium && aiData ? `
            <div id="aiGuideBlock" style="margin-top:12px;">
                <div style="padding:14px;background:linear-gradient(135deg, rgba(255,213,79,0.05), rgba(30,58,30,0.3));border-radius:12px;border:1px solid var(--color-gold);">
                    <span style="color:var(--color-gold);font-weight:600;font-size:14px;">${sanitizeHTML(aiData.guide_title)}</span>
                    <p style="font-size:12px;color:var(--color-text-light);margin-top:6px;line-height:1.7;">${sanitizeHTML(aiData.guide_energy)}</p>
                    <p style="font-size:12px;color:var(--color-text-light);margin-top:6px;line-height:1.7;">${sanitizeHTML(aiData.guide_advice)}</p>
                    <p style="font-size:12px;color:var(--color-gold);margin-top:10px;font-style:italic;line-height:1.7;">${sanitizeHTML(aiData.guide_affirmation)}</p>
                    <p style="font-size:11px;color:var(--color-text-lighter);margin-top:10px;line-height:1.6;">${sanitizeHTML(aiData.guide_whisper)}</p>
                </div>
            </div>` : (isPremium ? `
            <div id="personalCategories" style="margin-top:12px;">
                ${getPersonalCategoriesHtml(dayData.lunar_day, dayData.moon_zodiac)}
            </div>
            <div id="aiRecommendationBlock" style="margin-top:12px;"></div>` : '')}
            ${!isPremium ? `
            <div style="margin:16px 0;padding:16px;background:rgba(255,213,79,0.05);border:1px solid var(--color-gold);border-radius:16px;text-align:center;">
                <p style="font-size:13px;color:var(--color-gold);font-weight:600;margin-bottom:8px;">🔮 Полный лунный путеводитель</p>
                <p style="font-size:12px;color:var(--color-text-lighter);margin-bottom:12px;line-height:1.6;">
                    Детальные рекомендации, персональные ритуалы, советы по стрижкам и здоровью для каждого лунного дня.
                </p>
                <button class="btn btn-share btn-sm" onclick="showPaywall()" style="width:100%;">Открыть всё — ${window.paywallPrice || 599} ₽</button>
            </div>` : ''}
            <div id="moonChatBlock" style="margin-top:20px;max-width:100%;box-sizing:border-box;">
                <p style="font-weight:600;color:var(--color-gold);margin-bottom:4px;">Лунный день — это только начало</p>
                <p style="font-size:11px;color:var(--color-text-lighter);margin-bottom:12px;">Задайте вопрос о вашем дне</p>
                <div id="suggestedMoonQuestions" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px;">
                    <span style="font-size:12px;color:var(--color-text-light);">Загрузка подсказок...</span>
                </div>
                <div class="input-group" style="display:flex;gap:8px;">
                    <textarea id="moonQuestion" placeholder="Напишите свой вопрос..." maxlength="500"
                        style="resize:none;overflow:hidden;font-family:var(--font-main);font-size:14px;padding:10px 14px;border:2px solid var(--color-border);border-radius:12px;outline:none;color:var(--color-text);background:rgba(15,31,15,0.8);line-height:1.4;min-height:42px;transition:border-color 0.3s;width:100%;box-sizing:border-box;"></textarea>
                    <button class="btn btn-primary btn-sm" onclick="askMoonQuestion(${dayData.day})" style="flex-shrink:0;white-space:nowrap;">Спросить</button>
                </div>
                <div id="moonAnswer" style="margin-top:12px;max-width:100%;box-sizing:border-box;word-wrap:break-word;overflow-wrap:break-word;"></div>
            </div>
        </div>
    `;
    detail.scrollIntoView({ behavior: 'smooth', block: 'center' });

    if (isPremium && !aiData) {
        loadAIRecommendation(dayData.day);
    }

    setTimeout(() => {
        loadMoonQuestionSuggestions(dayData);
    }, 100);
}

// ============================================
// ПОДСКАЗКИ ВОПРОСОВ
// ============================================

function renderMoonSuggestions(container, suggestions) {
    // data-question — безопасный атрибут (не inline-JS), как в horoscope.html /
    // financial_code.html / compatibility.html / tarot_library.html.
    // Всё содержимое — через sanitizeHTML.
    container.innerHTML = suggestions.map(function(q) {
        var attrQ = String(q).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        return '<span class="moon-suggested-q" data-question="' + attrQ + '"'
            + ' style="display:inline-block;padding:8px 14px;font-size:12px;color:var(--color-text-light);cursor:pointer;background:rgba(30,58,30,0.8);border:1px solid var(--color-border);border-radius:18px;transition:all 0.2s ease;"'
            + ' onmouseover="this.style.borderColor=\'var(--color-gold)\';this.style.color=\'var(--color-gold)\';"'
            + ' onmouseout="this.style.borderColor=\'var(--color-border)\';this.style.color=\'var(--color-text-light)\';">'
            + sanitizeHTML(q) + '</span>';
    }).join('');

    if (!container.dataset.clickBound) {
        container.dataset.clickBound = '1';
        container.addEventListener('click', function(e) {
            var item = e.target.closest('.moon-suggested-q');
            if (item && item.dataset.question) {
                askSuggestedMoonQuestion(item.dataset.question);
            }
        });
    }
}

function loadMoonQuestionSuggestions(dayData) {
    const container = document.getElementById('suggestedMoonQuestions');
    if (!container) return;
    
    const dailyText = dayData.recommendation || '';
    
    fetch('/api/moon-calendar/suggestions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            lunar_day: dayData.lunar_day,
            phase_name: dayData.phase_name,
            moon_zodiac: dayData.moon_zodiac || '',
            daily_text: dailyText
        })
    })
    .then(r => r.json())
    .then(data => {
        const suggestions = data.suggestions || generateMoonQuestions(dayData);
        renderMoonSuggestions(container, suggestions);
    })
    .catch(() => {
        const suggestions = generateMoonQuestions(dayData);
        renderMoonSuggestions(container, suggestions);
    });
}

function generateMoonQuestions(dayData) {
    const lunarDay = dayData.lunar_day;
    const phase = dayData.phase_name;
    const zodiac = dayData.moon_zodiac || '';
    const dominant = (window.userTags && window.userTags.length > 0) ? window.userTags[0] : null;
    
    const phaseQuestions = {
        'Новолуние': [
            'Какое намерение стоит заложить в этом лунном цикле?',
            'Как использовать энергию обновления с пользой?',
            'Почему первый лунный день важен для старта?',
        ],
        'Полнолуние': [
            'Что стоит завершить, чтобы освободить место?',
            'Как пик лунной энергии влияет на планы?',
            'Какие тайны раскрывает полнолуние?',
        ],
        'Первая четверть': [
            'Как преодолеть сомнения и двигаться вперёд?',
            'Что говорят звёзды о текущих начинаниях?',
            'Почему важно не останавливаться на полпути?',
        ],
        'Последняя четверть': [
            'От чего стоит избавиться прямо сейчас?',
            'Какие уроки подводит этот лунный месяц?',
            'Что подготовить к новому лунному циклу?',
        ],
    };
    
    let question1 = '';
    if (phase in phaseQuestions) {
        const options = phaseQuestions[phase];
        question1 = options[lunarDay % options.length];
    } else {
        question1 = `Что ${lunarDay}-й лунный день значит для этого периода?`;
    }
    
    const zodiacQuestions = {
        'Овен': 'Какие решительные действия одобряет энергия дня?',
        'Телец': 'Как укрепить материальное положение в этот день?',
        'Близнецы': 'Какие встречи или разговоры изменят картину дня?',
        'Рак': 'Чему посвятить внимание в доме и семье?',
        'Лев': 'Как проявить себя ярко и без лишнего риска?',
        'Дева': 'Какой порядок навести в делах и мыслях?',
        'Весы': 'Как найти баланс между желаниями и обязанностями?',
        'Скорпион': 'Какие скрытые истины откроет этот день?',
        'Стрелец': 'Куда направить энергию для роста?',
        'Козерог': 'Какой шаг в карьере окажется самым верным?',
        'Водолей': 'Какая неожиданная идея принесёт прорыв?',
        'Рыбы': 'К чему прислушаться: интуиции или логике?',
    };
    const question2 = zodiacQuestions[zodiac] || 'Как использовать энергию этого дня?';
    
    const tagQuestions = {
        'love': [
            'Что день готовит для сферы отношений?',
            'Как привлечь гармонию и взаимность?',
            'Почему этот день важен для сердца?',
        ],
        'career': [
            'Какой карьерный шаг окажется успешным?',
            'Что мешает профессиональному росту сейчас?',
            'Какая встреча способна повлиять на карьеру?',
        ],
        'finance': [
            'Как привлечь денежный поток в этот день?',
            'Стоит ли планировать крупные покупки?',
            'Какой финансовый совет даёт лунный день?',
        ],
        'health': [
            'На что обратить внимание в самочувствии?',
            'Какие процедуры принесут максимум пользы?',
            'Как восстановить силы и энергию?',
        ],
        'spiritual': [
            'Какие практики усилят интуицию?',
            'О чём хочет сказать подсознание?',
            'Как услышать внутренний голос яснее?',
        ],
    };
    
    let question3 = 'Что советует лунный день по важным сферам?';
    if (dominant && dominant in tagQuestions) {
        const options = tagQuestions[dominant];
        question3 = options[lunarDay % options.length];
    }
    
    return [question1, question2, question3];
}

function askSuggestedMoonQuestion(question) {
    const input = document.getElementById('moonQuestion');
    if (input) {
        input.value = question;
        input.focus();
        input.style.height = 'auto';
        input.style.height = input.scrollHeight + 'px';
    }
}

async function askMoonQuestion(dayNum) {
    const question = document.getElementById('moonQuestion')?.value.trim();
    if (!question) return;

    const dayData = monthData.days[dayNum - 1];
    if (!dayData) return;

    const answerBlock = document.getElementById('moonAnswer');

    // Сообщение пользователя — справа (как было).
    answerBlock.innerHTML += `
        <div style="display:flex;justify-content:flex-end;margin-top:8px;">
            <div style="background:rgba(76,175,80,0.35);border-radius:18px 18px 4px 18px;padding:10px 16px;max-width:90%;font-size:14px;color:var(--color-text);line-height:1.5;word-wrap:break-word;overflow-wrap:break-word;">
                ${sanitizeHTML(question)}
            </div>
        </div>`;

    document.getElementById('moonQuestion').value = '';

    // Пузырь ответа — со «Печатает...», как было.
    const wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;justify-content:flex-start;margin-top:4px;';
    const bubble = document.createElement('div');
    bubble.style.cssText = 'background:rgba(30,58,30,0.6);border-radius:18px 18px 18px 4px;padding:10px 16px;max-width:90%;font-size:14px;color:var(--color-text-light);line-height:1.5;word-wrap:break-word;overflow-wrap:break-word;';
    bubble.textContent = 'Печатает...';
    wrap.appendChild(bubble);
    answerBlock.appendChild(wrap);
    answerBlock.scrollTop = answerBlock.scrollHeight;

    let firstChunk = true;

    await streamPost(
        '/api/moon-calendar/ask/stream',
        {
            question: question,
            lunar_day: dayData.lunar_day,
            phase_name: dayData.phase_name,
            moon_zodiac: dayData.moon_zodiac,
        },
        {
            onMeta: function(_meta) {
                // Метаданные (question) — можно использовать, но пока не нужно.
            },
            onChunk: function(data) {
                const chunk = data.chunk || '';
                if (firstChunk) {
                    bubble.textContent = '';
                    firstChunk = false;
                }
                bubble.textContent += chunk;
                answerBlock.scrollTop = answerBlock.scrollHeight;
            },
            onError: function(err) {
                if (firstChunk) {
                    // Ни одного чанка не пришло — используем пузырь для ошибки.
                    bubble.textContent = err.message || 'Что-то пошло не так. Попробуйте ещё раз.';
                    bubble.style.color = 'var(--color-error)';
                } else {
                    // Часть текста уже есть — допишем ошибку отдельным блоком.
                    answerBlock.insertAdjacentHTML('beforeend',
                        `<p style="color:var(--color-error);font-size:13px;margin-top:6px;">${sanitizeHTML(err.message || 'Ответ прервался.')}</p>`);
                }
            },
            onDone: function(_done) {
                // Текст уже накоплен в bubble.
            },
        }
    );
}

// ============================================
// ПЕРСОНАЛЬНЫЕ КАТЕГОРИИ
// ============================================

function getPersonalCategoriesHtml(lunarDay, moonZodiac) {
    const categories = getPersonalCategories(lunarDay, moonZodiac);
    if (categories.length === 0) return '';
    
    return categories.map(cat => `
        <div style="margin-bottom:16px;padding:0;background:transparent;border:none;">
            <span style="color:var(--color-gold);font-weight:600;font-size:12px;">${cat.title}</span>
            <p style="font-size:12px;color:var(--color-text-light);margin-top:2px;line-height:1.6;">${cat.desc}</p>
        </div>
    `).join('');
}

function getPersonalCategories(lunarDay, moonZodiac) {
    const allCategories = [];
    
    const lunarMap = {
        1: [{title: "Намерение дня", desc: "Запишите одно главное желание на этот лунный месяц. Энергия новолуния усилит его исполнение."}],
        2: [{title: "Чему научиться", desc: "День благоприятен для усвоения новой информации. Выделите 20 минут на обучение."}],
        3: [{title: "Точка силы", desc: "Самый активный день цикла. Направьте энергию на то, что давно откладывали."}],
        4: [{title: "Внутренний баланс", desc: "День равновесия. Уделите время и работе, и отдыху — в равных долях."}],
        5: [{title: "Творческий импульс", desc: "Займитесь тем, что приносит радость. Творчество сегодня лечит."}],
        6: [{title: "Знак судьбы", desc: "Обратите внимание на случайные встречи и совпадения — они не случайны."}],
        7: [{title: "Сила голоса", desc: "Слова сегодня имеют особую силу. Произнесите аффирмацию вслух."}],
        8: [{title: "Трансформация", desc: "День перемен. Смените причёску, переставьте мебель, попробуйте новое."}],
        9: [{title: "Защита энергии", desc: "Избегайте конфликтов и негативных людей. Ваше поле уязвимо."}],
        10: [{title: "Уют и корни", desc: "Проведите вечер с близкими. Приготовьте что-то вкусное, зажгите свечи."}],
        11: [{title: "Прорыв", desc: "День рекордов. Сделайте то, на что давно не решались."}],
        12: [{title: "Дар любви", desc: "Подарите подарок тому, кого любите. Маленький знак внимания принесёт большие перемены."}],
        13: [{title: "Магия дня", desc: "Зажгите благовония, помедитируйте. Дверь в подсознание открыта."}],
        14: [{title: "Подведение итогов", desc: "Завершите начатое до полнолуния. Подведите промежуточные итоги."}],
        15: [{title: "Пик силы", desc: "Полнолуние — время завершения. Отпустите то, что тянет назад."}],
        16: [{title: "Очищение", desc: "Сделайте генеральную уборку — в доме и в мыслях."}],
        17: [{title: "Маленький праздник", desc: "Встретьтесь с друзьями или устройте свидание с собой."}],
        18: [{title: "Зеркало души", desc: "Проанализируйте последние события. Какие уроки они принесли?"}],
        19: [{title: "Пауза", desc: "День тишины. Отдохните, выспитесь, не принимайте важных решений."}],
        20: [{title: "Открытие", desc: "Узнайте что-то новое. Прочитайте статью, посмотрите лекцию."}],
        21: [{title: "Движение вперёд", desc: "Благоприятный день для смены работы и новых проектов."}],
        22: [{title: "Наставничество", desc: "Поделитесь опытом. Напишите пост, дайте совет — это вернётся."}],
        23: [{title: "Избавление", desc: "Разберите шкаф, балкон, рабочий стол. Вместе с вещами уходит старое."}],
        24: [{title: "Природа", desc: "Выйдите на прогулку. Контакт с землёй и деревьями восстанавливает силы."}],
        25: [{title: "Дневник", desc: "Запишите мысли и чувства. Ведение дневника сегодня особенно целительно."}],
        26: [{title: "Диалог", desc: "День переговоров. Обсудите планы с коллегами или партнёром."}],
        27: [{title: "Водная магия", desc: "Примите ванну с солью, посетите спа. Вода смывает негатив."}],
        28: [{title: "Красота", desc: "День ухода за собой. Массаж, маска, новая косметика."}],
        29: [{title: "Прощение", desc: "Напишите письмо обидчику и сожгите. Отпустите прошлое."}],
        30: [{title: "Благодарность", desc: "Вспомните всё хорошее за этот лунный месяц. Поблагодарите мир."}],
    };
    
    if (lunarDay in lunarMap) {
        allCategories.push(...lunarMap[lunarDay]);
    }
    
    const mood = window.userTags || [];
    const dominant = mood.length > 0 ? mood[0] : null;
    
    const tagCategories = {
        'love': [
            {title: "Совет сердцу", desc: "Сегодня важно услышать не только себя, но и партнёра. Задайте вопрос и внимательно выслушайте ответ."},
            {title: "Знак от Вселенной", desc: "Обратите внимание на повторяющиеся цифры или имена — это подсказка в личной жизни."},
            {title: "Романтика дня", desc: "Маленький жест заботы сегодня значит больше, чем громкие слова. Сделайте первый шаг."},
            {title: "Примирение", desc: "Если есть недосказанность — сегодня звёзды помогут найти нужные слова для разговора."},
        ],
        'career': [
            {title: "Карьерный шаг", desc: "Запишите 3 цели на этот лунный месяц. Конкретные, измеримые, с дедлайном."},
            {title: "Нужный человек", desc: "Сегодня вероятна встреча, которая повлияет на карьеру. Будьте открыты к знакомствам."},
            {title: "Фокус дня", desc: "Одно важное дело сегодня стоит десяти мелких. Выберите главное и сделайте его."},
            {title: "Новая дверь", desc: "Присмотритесь к неожиданным предложениям. За случайностью может скрываться шанс."},
        ],
        'finance': [
            {title: "Денежный поток", desc: "Запишите все траты за день. Осознанность в финансах — первый шаг к изобилию."},
            {title: "Ваш ресурс", desc: "Какой навык приносит больше всего денег? Подумайте, как усилить его в ближайший месяц."},
            {title: "Тихая прибыль", desc: "Сегодня благоприятный день для пассивного дохода. Проверьте счета и накопления."},
            {title: "Умная покупка", desc: "Если планируете крупную покупку — сегодня хороший день сравнить цены и выбрать лучшее."},
        ],
        'health': [
            {title: "Тело и дух", desc: "Выделите 15 минут на растяжку или дыхательные упражнения. Тело скажет спасибо."},
            {title: "Энергия дня", desc: "Обратите внимание на питание. Лёгкая пища сегодня принесёт больше энергии, чем кофе."},
            {title: "Перезагрузка", desc: "Лучшее, что можно сделать сегодня для здоровья — лечь спать на час раньше обычного."},
            {title: "Движение", desc: "Прогулка в течение 20 минут улучшит настроение и запустит обмен веществ."},
        ],
        'spiritual': [
            {title: "Послание свыше", desc: "Запишите сон или предчувствие. Интуиция сегодня особенно сильна и не обманет."},
            {title: "Минута тишины", desc: "Посидите в тишине 10 минут. Ответ, который вы ищете, уже внутри вас."},
            {title: "Благодарность", desc: "Назовите трёх людей, которым вы благодарны. Это простое действие меняет вибрации дня."},
            {title: "Знаки вокруг", desc: "Обратите внимание на повторяющиеся события. Вселенная говорит с вами через совпадения."},
        ],
        'sad': [
            {title: "Утешение", desc: "Даже в пасмурный день есть свет. Позвольте себе отдохнуть — завтра будет легче."},
            {title: "Маленькая радость", desc: "Сделайте себе подарок: чашка любимого чая, фильм, тёплый плед. Вы заслуживаете заботы."},
            {title: "Тёплые мысли", desc: "Вспомните момент, когда вы были счастливы. Это воспоминание — ваш якорь в любой шторм."},
            {title: "После дождя", desc: "Грусть — это тоже часть пути. Разрешите себе чувствовать. Завтра будет новый день."},
        ],
    };
    
    if (dominant && dominant in tagCategories) {
        const options = tagCategories[dominant];
        const shuffled = options.sort(() => Math.random() - 0.5);
        const count = Math.min(shuffled.length, 2);
        allCategories.push(...shuffled.slice(0, count));
    }
    
    if (allCategories.length < 2) {
        allCategories.push(
            {title: "Совет дня", desc: "Прислушайтесь к себе. Сегодня важно сделать паузу и спросить: чего я хочу на самом деле?"},
            {title: "Энергия дня", desc: "Доверьтесь лунным ритмам. Даже в самый обычный день есть место чуду."}
        );
    }
    
    return allCategories.slice(0, 4);
}

// ============================================
// AI-РЕКОМЕНДАЦИЯ (СТАРАЯ, ДЛЯ FALLBACK)
// ============================================

async function loadAIRecommendation(dayNum) {
    const block = document.getElementById('aiRecommendationBlock');
    if (!block) return;
    block.innerHTML = '<p style="font-size:12px;color:var(--color-text-lighter);">✨ Загружаем персональную рекомендацию...</p>';

    try {
        const res = await fetch('/api/moon-calendar/day-ai', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                year: currentYear,
                month: currentMonth + 1,
                day: dayNum,
                timezone: getUserTimezone()
            })
        });
        const data = await res.json();

        if (data.error) {
            block.innerHTML = '';
            return;
        }

        if (data.ai_recommendation) {
            const lines = data.ai_recommendation.split('\n');
            const title = lines[0] || 'Ваш путеводитель';
            const body = lines.slice(2).join('<br>');
            
            const fontSize = window.userTariff === 'Пламя' ? '13px' : '11px';
            const lineHeight = window.userTariff === 'Пламя' ? '1.7' : '1.5';
            
            block.innerHTML = `
                <div style="padding:14px;background:linear-gradient(135deg, rgba(255,213,79,0.05), rgba(30,58,30,0.3));border-radius:12px;border:1px solid var(--color-gold);">
                    <span style="color:var(--color-gold);font-weight:600;font-size:14px;">${title}</span>
                    <p style="font-size:${fontSize};color:var(--color-text-light);margin-top:6px;line-height:${lineHeight};">${body}</p>
                </div>`;
        }
    } catch(e) {
        block.innerHTML = '';
    }
}

// ============================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ============================================

function getZodiacEmoji(zodiac) {
    const map = {
        'Овен': '♈', 'Телец': '♉', 'Близнецы': '♊', 'Рак': '♋',
        'Лев': '♌', 'Дева': '♍', 'Весы': '♎', 'Скорпион': '♏',
        'Стрелец': '♐', 'Козерог': '♑', 'Водолей': '♒', 'Рыбы': '♓'
    };
    return map[zodiac] || '';
}

function getPhaseEmoji(phaseName) {
    const map = {
        'Новолуние': '🌑',
        'Молодая Луна': '🌒',
        'Первая четверть': '🌓',
        'Прибывающая Луна': '🌔',
        'Полнолуние': '🌕',
        'Убывающая Луна': '🌖',
        'Последняя четверть': '🌗',
        'Старая Луна': '🌘'
    };
    return map[phaseName] || '';
}