(() => {
    document.querySelectorAll('.catalog-image-upload').forEach((widget) => {
        const input = widget.querySelector('input[type="file"]');
        const picker = widget.querySelector('.catalog-image-picker');
        const image = picker.querySelector('img');
        const placeholder = picker.querySelector('span');
        const error = widget.querySelector('.catalog-image-error');
        const clear = widget.querySelector('input[type="checkbox"]');
        let previewURL = null;
        function show() {
            if (previewURL) URL.revokeObjectURL(previewURL);
            previewURL = null;
            const file = input.files[0];
            let url = clear?.checked ? '' : widget.dataset.imageUrl || '';
            if (file && file.type.startsWith('image/')) {
                previewURL = URL.createObjectURL(file);
                url = previewURL;
            }
            if (url) image.src = url;
            else image.removeAttribute('src');
            image.hidden = !url;
            placeholder.hidden = !!url;
        }
        function receive(file) {
            if (!file) return;
            if (!file.type.startsWith('image/')) {
                error.textContent = 'Выбери файл изображения.';
                error.hidden = false;
                return;
            }
            try {
                const transfer = new DataTransfer();
                transfer.items.add(file);
                input.files = transfer.files;
                input.dispatchEvent(new Event('change', {bubbles: true}));
            } catch {
                error.textContent = 'Выбери картинку через кнопку выбора файла под окошком.';
                error.hidden = false;
            }
        }
        picker.addEventListener('click', () => input.click());
        input.addEventListener('change', () => {
            if (input.files.length && clear) clear.checked = false;
            error.hidden = true;
            show();
        });
        clear?.addEventListener('change', () => {
            if (clear.checked) input.value = '';
            show();
        });
        picker.addEventListener('paste', (event) => {
            const file = Array.from(event.clipboardData?.files || []).find((item) => item.type.startsWith('image/'));
            if (file) { event.preventDefault(); receive(file); }
        });
        picker.addEventListener('dragover', (event) => {
            event.preventDefault();
            picker.classList.add('is-dragging');
        });
        picker.addEventListener('dragleave', () => picker.classList.remove('is-dragging'));
        picker.addEventListener('drop', (event) => {
            event.preventDefault();
            picker.classList.remove('is-dragging');
            receive(event.dataTransfer?.files[0]);
        });
        show();
        window.addEventListener('pageshow', show);
        window.addEventListener('pagehide', () => {
            if (previewURL) URL.revokeObjectURL(previewURL);
            previewURL = null;
        });
    });
})();
