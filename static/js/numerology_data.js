// ============================================
// numerology_data.js — справочник чисел
// ============================================

// Асинхронная загрузка данных из JSON с кэшированием в sessionStorage
const NUMBER_DATA_LOADER = (function() {
    let _data = null;
    let _promise = null;

    function load() {
        if (_data) return Promise.resolve(_data);
        if (_promise) return _promise;

        // Пробуем sessionStorage
        try {
            const cached = sessionStorage.getItem('numerology_data');
            if (cached) {
                _data = JSON.parse(cached);
                return Promise.resolve(_data);
            }
        } catch(e) {}

        _promise = fetch('/static/data/numerology_data.json')
            .then(function(r) {
                if (!r.ok) throw new Error('Failed to load numerology_data.json');
                return r.json();
            })
            .then(function(json) {
                _data = json;
                try {
                    sessionStorage.setItem('numerology_data', JSON.stringify(json));
                } catch(e) {}
                return _data;
            })
            .catch(function() {
                // Fallback: пустая структура, чтобы не ломать остальной код
                _data = {
                    life_path: { title: 'Число Жизненного Пути', numbers: {} },
                    destiny: { title: 'Число Судьбы', numbers: {} },
                    soul_urge: { title: 'Число Души', numbers: {} },
                    personality: { title: 'Число Личности', numbers: {} },
                    maturity: { title: 'Число Зрелости', numbers: {} },
                    birth_day: { title: 'Число Дня Рождения', numbers: {} }
                };
                return _data;
            });

        return _promise;
    }

    return { load: load };
})();

// Для обратной совместимости: NUMBER_DATA будет заполнен асинхронно
var NUMBER_DATA = null;
NUMBER_DATA_LOADER.load().then(function(data) { NUMBER_DATA = data; });

// Константы (не зависят от данных)
var TYPE_NAMES = {
    life_path: 'Число Жизненного Пути',
    destiny: 'Число Судьбы',
    soul_urge: 'Число Души',
    personality: 'Число Личности',
    maturity: 'Число Зрелости',
    birth_day: 'Число Дня Рождения'
};

var ALL_TYPES = ['life_path', 'destiny', 'soul_urge', 'personality', 'maturity', 'birth_day'];


// ============================================
// МОДАЛЬНОЕ ОКНО СПРАВОЧНИКА ЧИСЕЛ
// ============================================

function openNumberInfo(typeKey, number) {
    // Ждём загрузки данных, если ещё не загружены
    if (!NUMBER_DATA) {
        NUMBER_DATA_LOADER.load().then(function() {
            openNumberInfo(typeKey, number);
        });
        return;
    }

    const data = NUMBER_DATA[typeKey];
    if (!data) return;
    const numData = data.numbers[number];
    if (!numData) return;
    const modal = document.getElementById('numberInfoModal');
    const content = document.getElementById('numberInfoContent');
    
    let tagsHtml = numData.tags.map(t => '<span style="display: inline-block; padding: 4px 12px; background: rgba(255,213,79,0.1); color: var(--color-gold); border-radius: 20px; font-size: 12px; margin: 2px; border: 1px solid var(--color-gold);">' + t + '</span>').join('');
    
    let otherTypesHtml = '';
    ALL_TYPES.forEach(t => {
        if (t !== typeKey && NUMBER_DATA[t] && NUMBER_DATA[t].numbers[number]) {
            otherTypesHtml += '<span onclick="openNumberInfo(\'' + t + '\', ' + number + ')" style="display: inline-block; padding: 8px 16px; background: transparent; border: 1px solid var(--color-border); border-radius: 8px; font-size: 12px; color: var(--color-text); cursor: pointer; transition: all 0.2s ease;" onmouseover="this.style.borderColor=\'var(--color-gold)\';this.style.color=\'var(--color-gold)\'" onmouseout="this.style.borderColor=\'var(--color-border)\';this.style.color=\'var(--color-text)\'">' + TYPE_NAMES[t] + ' ' + number + '</span>';
        }
    });
    
    let otherNumbersHtml = '';
    [1,2,3,4,5,6,7,8,9,11,22,33].forEach(n => {
        if (n !== number) {
            otherNumbersHtml += '<span onclick="openNumberInfo(\'' + typeKey + '\', ' + n + ')" style="display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; border-radius: 50%; background: var(--color-primary-soft); color: var(--color-primary-dark); font-weight: 600; font-size: 14px; cursor: pointer; transition: all 0.2s ease;" onmouseover="this.style.background=\'#d4879a\';this.style.color=\'white\'" onmouseout="this.style.background=\'var(--color-primary-soft)\';this.style.color=\'var(--color-primary-dark)\'">' + n + '</span>';
        }
    });
    
    content.innerHTML = `
        <div style="font-size: 48px; margin-bottom: 4px; color: var(--color-gold); font-weight: 300;">${number}</div>
        <h2 style="font-size: 16px; font-weight: 600; color: var(--color-text); margin-bottom: 2px;">${TYPE_NAMES[typeKey]} ${number}</h2>
        <p style="font-size: 14px; font-weight: 500; color: var(--color-gold); margin-bottom: 12px;">${numData.subtitle}</p>
        <div style="display: flex; flex-wrap: wrap; gap: 4px; justify-content: center; margin-bottom: 20px;">${tagsHtml}</div>
        
        <div style="text-align: left; margin-bottom: 16px; padding: 0; background: transparent; border: none;">
            <h3 style="font-size: 14px; font-weight: 600; color: var(--color-gold); margin-bottom: 6px;">Значение</h3>
            <p style="font-size: 14px; color: var(--color-text); line-height: 1.7;">${numData.meaning}</p>
        </div>
        
        <div style="text-align: left; margin-bottom: 16px; padding: 0; background: transparent; border: none;">
            <h3 style="font-size: 14px; font-weight: 600; color: #7eb89e; margin-bottom: 6px;">Сильные стороны</h3>
            <ul style="list-style: none; padding: 0; margin: 0;">
                ${numData.strengths.map(s => '<li style="font-size: 14px; color: var(--color-text); padding: 3px 0; line-height: 1.5;">• ' + s + '</li>').join('')}
            </ul>
        </div>
        
        <div style="text-align: left; margin-bottom: 20px; padding: 0; background: transparent; border: none;">
            <h3 style="font-size: 14px; font-weight: 600; color: #8b3a4a; margin-bottom: 6px;">Вызовы и трудности</h3>
            <ul style="list-style: none; padding: 0; margin: 0;">
                ${numData.challenges.map(c => '<li style="font-size: 14px; color: var(--color-text); padding: 3px 0; line-height: 1.5;">• ' + c + '</li>').join('')}
            </ul>
        </div>
        
        <div style="text-align: left; border-top: 1px solid var(--color-border); padding-top: 16px; margin-top: 16px;">
            <h3 style="font-size: 14px; font-weight: 600; color: var(--color-gold); margin-bottom: 8px;">Другие значения — ${TYPE_NAMES[typeKey]}</h3>
            <div style="display: flex; flex-wrap: wrap; gap: 6px; justify-content: center;">
                ${otherNumbersHtml}
            </div>
        </div>
        
        <div style="text-align: left; border-top: 1px solid var(--color-border); padding-top: 16px; margin-top: 16px;">
            <h3 style="font-size: 14px; font-weight: 600; color: var(--color-gold); margin-bottom: 8px;">Число ${number} в других аспектах</h3>
            <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                ${otherTypesHtml}
            </div>
        </div>
    `;
    
    modal.classList.add('active');
}

function closeNumberInfo() {
    document.getElementById('numberInfoModal').classList.remove('active');
}

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeNumberInfo();
});