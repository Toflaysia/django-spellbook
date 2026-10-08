function initDescriptionEditors() {
    'use strict';
    const PREFIX = 'SPELLBOOK_BLOCKS_V1:';
    const make = (tag, className, text) => {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    };
    function plainText(node) {
        let result = '';
        function walk(item) {
            if (item.nodeType === Node.TEXT_NODE) {
                result += item.textContent;
                return;
            }
            if (item.nodeType !== Node.ELEMENT_NODE) return;
            if (item.tagName === 'BR') { result += '\n'; return; }
            const block = ['DIV', 'P', 'LI'].includes(item.tagName);
            if (block && result && !result.endsWith('\n')) result += '\n';
            Array.from(item.childNodes).forEach(walk);
            if (block && !result.endsWith('\n')) result += '\n';
        }
        Array.from(node.childNodes).forEach(walk);
        return result.replace(/\n$/, '');
    }
    function setText(node, value) {
        value.split('\n').forEach((line, index) => {
            if (index) node.append(document.createElement('br'));
            node.append(document.createTextNode(line));
        });
        if (!value) node.append(document.createElement('br'));
    }
    document.querySelectorAll('textarea[data-description-editor]').forEach((source) => {
        if (source.dataset.editorReady) return;
        let initial;
        try {
            initial = source.value.startsWith(PREFIX)
                ? JSON.parse(source.value.slice(PREFIX.length))
                : [{type: 'text', text: source.value}];
            if (!Array.isArray(initial) || !initial.every((block) =>
                block && ((block.type === 'text' && typeof block.text === 'string') ||
                (block.type === 'table' && Array.isArray(block.rows) &&
                block.rows.length > 0 && block.rows.length <= 9 &&
                Array.isArray(block.rows[0]) && block.rows[0].length > 0 &&
                block.rows[0].length <= 9 && block.rows.every((row) =>
                Array.isArray(row) && row.length === block.rows[0].length &&
                row.every((cell) => typeof cell === 'string')))))) return;
        } catch { return; }
        source.dataset.editorReady = 'true';
        const required = source.required;
        const editor = make('div', 'description-editor');
        const toolbar = make('div', 'description-toolbar');
        const dropdown = make('div', 'description-dropdown');
        const menu = make('div', 'description-menu');
        menu.hidden = true;
        menu.id = `${source.id}-table-menu`;
        const surface = make('div', 'description-surface');
        surface.contentEditable = 'true';
        surface.id = `${source.id}-editor`;
        surface.setAttribute('role', 'textbox');
        surface.setAttribute('aria-multiline', 'true');
        surface.setAttribute('aria-required', String(required));
        surface.setAttribute('aria-label', source.labels[0]?.textContent.trim() || 'Описание');
        const error = make('div', 'description-editor-error');
        error.hidden = true;
        error.setAttribute('role', 'alert');
        let savedRange = null;
        let activeCell = null;
        const tableButtons = [];
        function button(text, callback, label = text) {
            const node = make('button', 'description-small-button', text);
            node.type = 'button';
            node.title = label;
            node.setAttribute('aria-label', label);
            node.addEventListener('mousedown', (event) => event.preventDefault());
            node.addEventListener('click', callback);
            return node;
        }
        function remember() {
            const selection = window.getSelection();
            if (!selection.rangeCount) return;
            const range = selection.getRangeAt(0);
            if (surface.contains(range.startContainer) && surface.contains(range.endContainer)) {
                savedRange = range.cloneRange();
                const parent = range.startContainer.nodeType === Node.ELEMENT_NODE
                    ? range.startContainer : range.startContainer.parentElement;
                activeCell = parent.closest('td');
                if (activeCell && !surface.contains(activeCell)) activeCell = null;
                updateControls();
            }
        }
        function caret(node, end = false) {
            const range = document.createRange();
            range.selectNodeContents(node);
            range.collapse(!end);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            surface.focus();
            remember();
        }
        function restore() {
            surface.focus();
            const range = savedRange && surface.contains(savedRange.startContainer)
                && surface.contains(savedRange.endContainer) ? savedRange.cloneRange()
                : document.createRange();
            if (!savedRange || !surface.contains(range.startContainer)) {
                range.selectNodeContents(surface);
                range.collapse(false);
            }
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            return range;
        }
        function createCell(value = '') {
            const cell = document.createElement('td');
            setText(cell, value);
            return cell;
        }
        function createTable(rows) {
            const table = make('table', 'description-edit-table');
            const body = document.createElement('tbody');
            rows.forEach((values) => {
                const row = document.createElement('tr');
                values.forEach((value) => row.append(createCell(value)));
                body.append(row);
            });
            table.append(body);
            return table;
        }
        function collect() {
            const blocks = [];
            let text = '';
            function flush() {
                if (text.trim()) blocks.push({type: 'text', text: text.replace(/^\n+|\n+$/g, '')});
                text = '';
            }
            function walk(node) {
                if (node.nodeType === Node.TEXT_NODE) { text += node.textContent; return; }
                if (node.nodeType !== Node.ELEMENT_NODE) return;
                if (node.tagName === 'TABLE') {
                    flush();
                    blocks.push({type: 'table', rows: Array.from(node.rows).map((row) =>
                        Array.from(row.cells).map(plainText))});
                    return;
                }
                if (node.tagName === 'BR') { text += '\n'; return; }
                const block = ['DIV', 'P', 'LI'].includes(node.tagName);
                if (block && text && !text.endsWith('\n')) text += '\n';
                Array.from(node.childNodes).forEach(walk);
                if (block && !text.endsWith('\n')) text += '\n';
            }
            Array.from(surface.childNodes).forEach(walk);
            flush();
            return blocks;
        }
        function sync() {
            const blocks = collect();
            source.value = blocks.some((block) => block.type === 'table')
                ? PREFIX + JSON.stringify(blocks)
                : blocks.map((block) => block.text).join('\n\n');
            error.hidden = true;
            surface.removeAttribute('aria-invalid');
            updateControls();
        }
        function currentTable() {
            return activeCell?.isConnected && surface.contains(activeCell)
                ? activeCell.closest('table') : null;
        }
        function updateControls() {
            const table = currentTable();
            tableButtons.forEach(([node, action]) => {
                node.hidden = !table;
                node.disabled = !table ||
                    (action === 'row-add' && table.rows.length >= 9) ||
                    (action === 'column-add' && table.rows[0].cells.length >= 9) ||
                    (action === 'row-delete' && table.rows.length <= 1) ||
                    (action === 'column-delete' && table.rows[0].cells.length <= 1);
            });
        }
        function closeMenu() {
            menu.hidden = true;
            toggle.setAttribute('aria-expanded', 'false');
        }
        const toggle = button('▾', () => {
            menu.hidden = !menu.hidden;
            toggle.setAttribute('aria-expanded', String(!menu.hidden));
            if (!menu.hidden) insert.focus();
        }, 'Добавить таблицу');
        toggle.className = 'description-toggle';
        toggle.setAttribute('aria-controls', menu.id);
        toggle.setAttribute('aria-expanded', 'false');
        const insert = button('Таблица', () => {
            let range = restore();
            if (currentTable()) {
                range = document.createRange();
                range.setStartAfter(currentTable());
                range.collapse(true);
            }
            range.deleteContents();
            // Split the surrounding text at the caret; tables stay at the root.
            const tail = range.cloneRange();
            tail.setEnd(surface, surface.childNodes.length);
            const fragment = tail.extractContents();
            const table = createTable([['', ''], ['', '']]);
            const after = document.createElement('p');
            after.append(document.createElement('br'));
            surface.append(table, after, fragment);
            closeMenu();
            caret(table.rows[0].cells[0]);
            sync();
        });
        menu.append(insert);
        dropdown.append(toggle, menu);
        toolbar.append(dropdown);
        function tableAction(text, action, callback) {
            const node = button(text, () => {
                if (!currentTable()) return;
                callback(currentTable());
                sync();
            });
            tableButtons.push([node, action]);
            toolbar.append(node);
        }
        tableAction('+ Строка', 'row-add', (table) => {
            if (table.rows.length >= 9) return;
            const row = table.insertRow(activeCell.parentElement.rowIndex + 1);
            for (let index = 0; index < table.rows[0].cells.length; index++) row.append(createCell());
            caret(row.cells[0]);
        });
        tableAction('+ Столбец', 'column-add', (table) => {
            if (table.rows[0].cells.length >= 9) return;
            const index = activeCell.cellIndex + 1;
            const rowIndex = activeCell.parentElement.rowIndex;
            Array.from(table.rows).forEach((row) => row.insertBefore(createCell(), row.cells[index] || null));
            caret(table.rows[rowIndex].cells[index]);
        });
        tableAction('Удалить строку', 'row-delete', (table) => {
            if (table.rows.length <= 1) return;
            const index = activeCell.parentElement.rowIndex;
            table.deleteRow(index);
            caret(table.rows[Math.min(index, table.rows.length - 1)].cells[0]);
        });
        tableAction('Удалить столбец', 'column-delete', (table) => {
            if (table.rows[0].cells.length <= 1) return;
            const index = activeCell.cellIndex;
            const rowIndex = activeCell.parentElement.rowIndex;
            Array.from(table.rows).forEach((row) => row.deleteCell(index));
            caret(table.rows[rowIndex].cells[Math.min(index, table.rows[0].cells.length - 1)]);
        });
        tableAction('Удалить таблицу', 'table-delete', (table) => {
            const paragraph = document.createElement('p');
            paragraph.append(document.createElement('br'));
            table.replaceWith(paragraph);
            activeCell = null;
            caret(paragraph);
        });
        initial.forEach((block) => {
            if (block.type === 'table') surface.append(createTable(block.rows));
            else {
                const paragraph = document.createElement('p');
                setText(paragraph, block.text);
                surface.append(paragraph);
            }
        });
        if (!surface.lastElementChild || surface.lastElementChild.tagName === 'TABLE') {
            const paragraph = document.createElement('p');
            paragraph.append(document.createElement('br'));
            surface.append(paragraph);
        }
        editor.append(toolbar, surface, error);
        source.after(editor);
        source.hidden = true;
        source.required = false;
        source.labels.forEach((label) => label.htmlFor = surface.id);
        document.addEventListener('selectionchange', remember);
        surface.addEventListener('input', sync);
        surface.addEventListener('focus', remember);
        function insertPlain(value) {
            const range = restore();
            range.deleteContents();
            const fragment = document.createDocumentFragment();
            setText(fragment, value);
            const last = fragment.lastChild;
            range.insertNode(fragment);
            range.setStartAfter(last);
            range.collapse(true);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            remember();
            sync();
        }
        surface.addEventListener('paste', (event) => {
            event.preventDefault();
            remember();
            insertPlain(event.clipboardData.getData('text/plain'));
        });
        surface.addEventListener('drop', (event) => event.preventDefault());
        surface.addEventListener('keydown', (event) => {
            remember();
            if (event.key === 'Enter' && activeCell) {
                event.preventDefault();
                insertPlain('\n');
            }
            if (event.key !== 'Tab' || !activeCell || event.ctrlKey || event.metaKey || event.altKey) return;
            const table = currentTable();
            const cells = Array.from(table.querySelectorAll('td'));
            const index = cells.indexOf(activeCell);
            const next = index + (event.shiftKey ? -1 : 1);
            if (cells[next]) { event.preventDefault(); caret(cells[next]); }
            else if (!event.shiftKey && table.rows.length < 9) {
                event.preventDefault();
                const row = table.insertRow();
                for (let column = 0; column < table.rows[0].cells.length; column++) row.append(createCell());
                caret(row.cells[0]);
                sync();
            } else if (!event.shiftKey) {
                event.preventDefault();
                let paragraph = table.nextElementSibling;
                if (!paragraph) {
                    paragraph = document.createElement('p');
                    paragraph.append(document.createElement('br'));
                    table.after(paragraph);
                }
                caret(paragraph);
            }
        });
        dropdown.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') { closeMenu(); toggle.focus(); }
        });
        document.addEventListener('click', (event) => {
            if (!dropdown.contains(event.target)) closeMenu();
        });
        source.form.addEventListener('submit', (event) => {
            sync();
            const hasContent = collect().some((block) => block.type === 'text'
                ? block.text.trim() : block.rows.some((row) => row.some((cell) => cell.trim())));
            if (required && !hasContent) {
                event.preventDefault();
                const section = editor.closest('[role="tabpanel"]');
                if (section?.hidden) {
                    document.querySelector(`[aria-controls="${section.id}"]`)?.click();
                }
                error.textContent = 'Заполни описание.';
                error.hidden = false;
                surface.setAttribute('aria-invalid', 'true');
                if (!source.form.querySelector('.description-surface[aria-invalid="true"]:focus')) surface.focus();
            }
        });
        updateControls();
    });
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDescriptionEditors, {once: true});
} else {
    initDescriptionEditors();
}
