// tracker.js — отслеживание поведения пользователя
(function() {
    'use strict';
    
    const events = [];
    const SEND_INTERVAL = 30000; // 30 секунд
    const SECTION_ATTR = 'data-numer-section'; // атрибут на HTML-элементах разделов
    
    function getCurrentSection() {
        const el = document.querySelector(`[${SECTION_ATTR}]`);
        return el ? el.getAttribute(SECTION_ATTR) : 'unknown';
    }
    
    function track(type, metadata = {}) {
        events.push({
            type: type,
            section: getCurrentSection(),
            metadata: metadata,
            timestamp: new Date().toISOString()
        });
    }
    
    function sendEvents() {
        if (events.length === 0) return;
        
        const batch = events.splice(0, events.length);
        fetch('/api/track', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ events: batch }),
            keepalive: true
        }).catch(() => {});
    }
    
    // Отслеживание кликов по важным элементам
    document.addEventListener('click', function(e) {
        const target = e.target.closest('[data-numer-track]');
        if (target) {
            const trackType = target.getAttribute('data-numer-track');
            const trackMeta = target.getAttribute('data-numer-meta') || '{}';
            try {
                track(trackType, JSON.parse(trackMeta));
            } catch {
                track(trackType, { value: trackMeta });
            }
        }
    }, true);
    
    // Отслеживание скролла — раз в 5 секунд фиксируем глубину
    let lastScrollTime = 0;
    window.addEventListener('scroll', function() {
        const now = Date.now();
        if (now - lastScrollTime < 5000) return;
        lastScrollTime = now;
        
        const scrollPercent = Math.round(
            (window.scrollY + window.innerHeight) / document.documentElement.scrollHeight * 100
        );
        track('scroll', { depth: scrollPercent });
    }, { passive: true });
    
    // Отслеживание времени на странице
    let pageEnterTime = Date.now();
    window.addEventListener('beforeunload', function() {
        const timeSpent = Math.round((Date.now() - pageEnterTime) / 1000);
        track('page_exit', { time_spent_seconds: timeSpent });
        sendEvents();
    });
    
    // Отслеживание видимости разделов через IntersectionObserver
    const observedSections = new Set();
    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting && !observedSections.has(entry.target)) {
                observedSections.add(entry.target);
                const sectionName = entry.target.getAttribute(SECTION_ATTR);
                if (sectionName) {
                    track('section_view', { section: sectionName });
                }
            }
        });
    }, { threshold: 0.3 });
    
    // Наблюдаем за элементами с data-unanum-section
    document.querySelectorAll(`[${SECTION_ATTR}]`).forEach(function(el) {
        observer.observe(el);
    });
    
    // Периодическая отправка событий
    setInterval(sendEvents, SEND_INTERVAL);
    
    // Отмечаем вход на страницу
    track('page_enter', { url: window.location.pathname });
    
})();