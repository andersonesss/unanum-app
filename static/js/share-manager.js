// ============================================
// SHARE MANAGER — единый модуль для всех страниц
// ============================================

let shareSelectedSentences = [];
let shareBar = null;

// Инициализация: ждём появления результатов на странице
(function initShareManager() {
    const observer = new MutationObserver(function(mutations) {
        for (const mutation of mutations) {
            if (mutation.addedNodes.length > 0) {
                const resultBlocks = document.querySelectorAll('.panel-result, #result-financial-code, #result-horoscope, #result-compatibility, #result-numerology, #result-natal-chart');
                for (const block of resultBlocks) {
                    if (block.children.length > 0 && !block.dataset.shareReady) {
                        block.dataset.shareReady = '1';
                        enhanceBlockForShare(block);
                    }
                }
            }
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
})();

function enhanceBlockForShare(container) {
    function wrapSentencesInTextNode(textNode) {
        const text = textNode.textContent;
        if (!text.trim() || text.trim().length < 3) return;
        
        const parts = text.match(/[^.!?]+[.!?]+/g);
        if (!parts || parts.length <= 1) {
            const span = document.createElement('span');
            span.className = 'share-sentence';
            span.dataset.text = text.trim();
            span.textContent = text;
            span.addEventListener('click', function(e) {
                e.stopPropagation();
                toggleShareSentence(this, this.dataset.text);
            });
            textNode.parentNode.replaceChild(span, textNode);
            return;
        }
        
        const fragment = document.createDocumentFragment();
        parts.forEach(part => {
            const trimmed = part.trim();
            if (trimmed.length < 3) {
                fragment.appendChild(document.createTextNode(part));
                return;
            }
            const span = document.createElement('span');
            span.className = 'share-sentence';
            span.dataset.text = trimmed;
            span.textContent = part;
            span.addEventListener('click', function(e) {
                e.stopPropagation();
                toggleShareSentence(this, this.dataset.text);
            });
            fragment.appendChild(span);
        });
        textNode.parentNode.replaceChild(fragment, textNode);
    }
    
    function walkAndWrap(node) {
        if (node.nodeType === 3) {
            wrapSentencesInTextNode(node);
        } else if (node.nodeType === 1) {
            if (node.closest('button') || node.closest('.btn') || node.closest('a')) return;
            if (node.closest('h1') || node.closest('h2') || node.closest('h3') || node.closest('h4')) return;
            if (node.classList.contains('share-sentence')) return;
            if (node.closest('#shareBar')) return;
            if (node.closest('textarea') || node.closest('input') || node.closest('select')) return;
            if (node.closest('[onclick*="showPaywall"]') || node.closest('[onclick*="paywall"]')) return;
            
            Array.from(node.childNodes).forEach(child => walkAndWrap(child));
        }
    }
    
    walkAndWrap(container);
}

function createShareBar() {
    if (shareBar) return;
    shareBar = document.createElement('div');
    shareBar.id = 'shareBar';
    shareBar.style.cssText = `
        position: fixed;
        bottom: 80px;
        left: 0;
        right: 0;
        background: var(--color-primary-soft);
        border-top: 2px solid var(--color-gold);
        padding: 12px 16px;
        z-index: 998;
        display: none;
        box-shadow: 0 -4px 20px rgba(0,0,0,0.4);
    `;
    shareBar.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
            <p style="font-size:12px;color:var(--color-text-light);margin:0;">
                Выбрано: <strong id="shareCount">0</strong>
            </p>
            <button onclick="clearShareSelection()" style="background:none;border:none;font-size:22px;cursor:pointer;color:var(--color-text-lighter);padding:0 4px;line-height:1;">&times;</button>
        </div>
        <button class="btn btn-share" onclick="doShareCard()" style="width:100%;">Поделиться в сториз</button>
    `;
    document.body.appendChild(shareBar);
}

function updateShareBar() {
    if (!shareBar) createShareBar();
    const count = shareSelectedSentences.length;
    const countEl = document.getElementById('shareCount');
    if (countEl) countEl.textContent = count;
    shareBar.style.display = count > 0 ? 'block' : 'none';
}

function clearShareSelection() {
    document.querySelectorAll('.share-sentence.selected').forEach(el => el.classList.remove('selected'));
    shareSelectedSentences = [];
    updateShareBar();
}

function toggleShareSentence(el, text) {
    if (el.classList.contains('selected')) {
        el.classList.remove('selected');
        shareSelectedSentences = shareSelectedSentences.filter(s => s !== text);
    } else {
        el.classList.add('selected');
        if (!shareSelectedSentences.includes(text)) {
            shareSelectedSentences.push(text);
        }
    }
    updateShareBar();
}

function doShareCard() {
    if (shareSelectedSentences.length === 0) return;
    clearShareSelection();
    
    // Заглушка — скоро в обновлениях
    const modal = document.createElement('div');
    modal.className = 'modal-overlay active';
    modal.style.zIndex = '600';
    modal.innerHTML = `
        <div class="modal" style="max-width:360px;text-align:center;">
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">&times;</button>
            <div style="font-size:48px;margin-bottom:12px;">✨</div>
            <h2 style="font-size:18px;color:var(--color-gold);margin-bottom:8px;">Скоро в обновлениях!</h2>
            <p style="font-size:13px;color:var(--color-text-light);line-height:1.6;">Возможность делиться результатами в сториз появится в ближайшем обновлении.</p>
            <button class="btn btn-primary btn-sm" onclick="this.closest('.modal-overlay').remove()" style="margin-top:12px;width:100%;">Понятно</button>
        </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
}