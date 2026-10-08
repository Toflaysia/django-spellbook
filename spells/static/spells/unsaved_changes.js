(() => {
    function init() {
        if (!document.querySelector('[data-confirm-unsaved]')) return;
        const form = document.querySelector('main form[method="post"]');
        if (!form) return;
        const message = 'У вас есть несохранённые изменения. Если уйти, они будут потеряны. Выйти без сохранения?';
        function snapshot() {
            return JSON.stringify(Array.from(new FormData(form), ([name, value]) => {
                if (name === 'csrfmiddlewaretoken') return null;
                return [name, value instanceof File
                    ? [value.name, value.size, value.name ? value.lastModified : 0, value.type]
                    : value];
            }).filter(Boolean));
        }
        const initial = snapshot();
        let leaving = false;
        const dirty = () => !leaving && snapshot() !== initial;
        window.addEventListener('pageshow', () => { leaving = false; });
        form.addEventListener('input', () => { leaving = false; });
        form.addEventListener('change', () => { leaving = false; });
        document.addEventListener('click', (event) => {
            const link = event.target.closest('a[href]');
            if (!link || event.defaultPrevented || event.button !== 0 ||
                event.ctrlKey || event.metaKey || event.shiftKey || event.altKey ||
                link.hasAttribute('download') || (link.target && link.target !== '_self')) return;
            const target = new URL(link.href, location.href);
            if (!['http:', 'https:'].includes(target.protocol)) return;
            if (target.origin === location.origin && target.pathname === location.pathname &&
                target.search === location.search && target.hash) return;
            if (!dirty()) return;
            if (!window.confirm(message)) {
                event.preventDefault();
                return;
            }
            queueMicrotask(() => { if (!event.defaultPrevented) leaving = true; });
        });
        document.addEventListener('submit', (event) => {
            if (event.target !== form && dirty() && !window.confirm(message)) {
                event.preventDefault();
                return;
            }
            // Wait for description editors and validation handlers to finish.
            queueMicrotask(() => { if (!event.defaultPrevented) leaving = true; });
        });
        window.addEventListener('beforeunload', (event) => {
            if (dirty()) {
                event.preventDefault();
                event.returnValue = '';
            }
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => queueMicrotask(init));
    } else {
        queueMicrotask(init);
    }
})();
