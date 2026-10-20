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
            if (item.dataset.spellToken) { result += item.dataset.spellToken; return; }
            if (item.tagName === 'BR') { result += '\n'; return; }
            const block = ['DIV', 'P', 'LI'].includes(item.tagName);
            if (block && result && !result.endsWith('\n')) result += '\n';
            Array.from(item.childNodes).forEach(walk);
            if (block && !result.endsWith('\n')) result += '\n';
        }
        Array.from(node.childNodes).forEach(walk);
        return result.replace(/\n$/, '');
    }
    function prepareLink(link) {
        link.contentEditable='false';link.tabIndex=0;link.setAttribute('role','button');
        link.title='Изменить текст ссылки';link.setAttribute('aria-label','Изменить текст ссылки: '+link.textContent);
    }
    function setText(node, value) {
        value.split('\n').forEach((line, index) => {
            if (index) node.append(document.createElement('br'));
            let last = 0;
            for (const match of line.matchAll(/\[\[(spell|damage|condition|school|dice|trait|effect|class|component|time):([^\]|\n]{1,160})\|([^\]\n]*)\]\]/g)) {
                node.append(document.createTextNode(line.slice(last, match.index)));
                const link = make('span', match[1]==='dice'?'description-dice-link':'description-spell-link');
                try { link.textContent = decodeURIComponent(match[3]); } catch { link.textContent = match[3]; }
                link.dataset.spellToken = match[0];
                prepareLink(link);
                node.append(link);
                last = match.index + match[0].length;
            }
            node.append(document.createTextNode(line.slice(last)));
        });
        if (!value) node.append(document.createElement('br'));
    }
    document.querySelectorAll('textarea[data-description-editor], textarea[name*="description"], textarea[name="higher_level"]').forEach((source) => {
        if (source.dataset.editorReady) return;
        let initial;
        try {
            initial = source.value.startsWith(PREFIX)
                ? JSON.parse(source.value.slice(PREFIX.length))
                : [{type: 'text', text: source.value}];
            if (!Array.isArray(initial) || !initial.every((block) =>
                block && ((['text','heading','quote'].includes(block.type) && typeof block.text === 'string') ||
                block.type === 'rule' || (block.type === 'list' && Array.isArray(block.items) && block.items.every(item => typeof item === 'string')) ||
                (block.type === 'table' && Array.isArray(block.rows) &&
                block.rows.length > 0 &&
                Array.isArray(block.rows[0]) && block.rows[0].length > 0 &&
                block.rows.every((row) =>
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
            // Focusing the surface can fire selectionchange; retain the original caret first.
            const previous=savedRange?.cloneRange();
            surface.focus();
            const valid=previous&&surface.contains(previous.startContainer)&&surface.contains(previous.endContainer);
            const range=valid?previous:document.createRange();
            if(!valid){range.selectNodeContents(surface);range.collapse(false);}
            const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);
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
                if (node.dataset.spellToken) { text += node.dataset.spellToken; return; }
                if (['HR','H3','BLOCKQUOTE','UL'].includes(node.tagName)) {
                    flush();
                    if (node.tagName === 'HR') blocks.push({type:'rule'});
                    else if (node.tagName === 'UL') {
                        const items=Array.from(node.children).map(plainText).filter(item=>item.trim());
                        if(items.length)blocks.push({type:'list',items});
                    } else {
                        const value=plainText(node);
                        if(value.trim())blocks.push({type:node.tagName==='H3'?'heading':'quote',text:value});
                    }
                    return;
                }
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
            source.value = blocks.some((block) => block.type !== 'text')
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
            if (!menu.hidden) menu.querySelector('button')?.focus();
        }, 'Форматирование и ссылки');
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
        function insertToken(kind,identifier,label) {
            const range=restore();range.deleteContents();
            const link=make('span',kind==='dice'?'description-dice-link':'description-spell-link',label);
            prepareLink(link);
            link.dataset.spellToken=`[[${kind}:${encodeURIComponent(identifier)}|${encodeURIComponent(label)}]]`;
            range.insertNode(link);const spacer=document.createTextNode(' ');link.after(spacer);range.setStartAfter(spacer);range.collapse(true);
            const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);
            remember();sync();source.dispatchEvent(new Event('input',{bubbles:true}));
        }
        async function insertReference(kind,pick) {
            remember();const selected=savedRange?.toString() || '';
            closeMenu();const item=await pick();
            if(!item)return;
            const label=await window.Spellbook.pickLinkLabel(selected || item.name);
            if(label!==null)insertToken(kind,item.id,label);
        }
        const insertSpell=button('Заклинание',()=>insertReference('spell',()=>window.Spellbook.pickSpell()));
        const insertDamage=button('Тип урона',()=>insertReference('damage',()=>window.Spellbook.pickCatalog('damage-types')));
        const insertCondition=button('Состояние',()=>insertReference('condition',()=>window.Spellbook.pickCatalog('conditions')));
        const insertTrait=button('Черта',()=>insertReference('trait',()=>window.Spellbook.pickCatalog('traits')));
        const insertSchool=button('Школа магии',()=>insertReference('school',()=>window.Spellbook.pickCatalog('schools')));
        async function editReference(link) {
            const token=link.dataset.spellToken.match(/^\[\[(spell|damage|condition|school|dice|trait|effect|class|component|time):([^|]+)\|[^\n]*\]\]$/);
            if(!token)return;
            const label=await window.Spellbook.pickLinkLabel(link.textContent,true);
            if(label===null||!link.isConnected)return;
            link.textContent=label;link.dataset.spellToken=`[[${token[1]}:${token[2]}|${encodeURIComponent(label)}]]`;
            prepareLink(link);sync();source.dispatchEvent(new Event('input',{bubbles:true}));
        }
        surface.addEventListener('click',event=>{const link=event.target.closest('[data-spell-token]');if(link)editReference(link);});
        surface.addEventListener('keydown',event=>{
            if((event.key==='Enter'||event.key===' ')&&event.target.matches('[data-spell-token]')){event.preventDefault();editReference(event.target);}
        });
        const insertDice=button('Кубики',async()=>{
            closeMenu();const expression=await window.Spellbook?.pickDice();
            if(expression)insertToken('dice',expression,expression);
        });
        function insertFormat(kind) {
            const range=restore();
            if(currentTable()) { closeMenu(); return; }
            const selected=range.toString();
            range.deleteContents();
            const tail=range.cloneRange();tail.setEnd(surface,surface.childNodes.length);
            const fragment=tail.extractContents();
            const node=document.createElement({rule:'hr',heading:'h3',quote:'blockquote',list:'ul'}[kind]);
            if(kind==='list') {
                (selected?selected.split('\n'):['']).forEach(value=>{const item=document.createElement('li');setText(item,value);node.append(item);});
            } else if(kind!=='rule')setText(node,selected);
            const after=document.createElement('p');after.append(document.createElement('br'));
            surface.append(node,after,fragment);closeMenu();
            caret(kind==='rule'?after:kind==='list'?node.firstChild:node);
            sync();source.dispatchEvent(new Event('input',{bubbles:true}));
        }
        menu.append(insert,insertSpell,insertDice,insertDamage,insertCondition,insertTrait,insertSchool,
            button('Линия',()=>insertFormat('rule')),
            button('Подзаголовок',()=>insertFormat('heading')),
            button('Список',()=>insertFormat('list')),
            button('Цитата',()=>insertFormat('quote')));
        menu.replaceChildren(...Array.from(menu.children).sort((a,b)=>a.textContent.localeCompare(b.textContent,'ru')));

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
            const row = table.insertRow(activeCell.parentElement.rowIndex + 1);
            for (let index = 0; index < table.rows[0].cells.length; index++) row.append(createCell());
            caret(row.cells[0]);
        });
        tableAction('+ Столбец', 'column-add', (table) => {
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
            if (block.type === 'rule')surface.append(document.createElement('hr'));
            else if (block.type === 'list') {
                const list=document.createElement('ul');
                block.items.forEach(value=>{const item=document.createElement('li');setText(item,value);list.append(item);});surface.append(list);
            }
            else if (block.type === 'heading' || block.type === 'quote') {
                const node=document.createElement(block.type==='heading'?'h3':'blockquote');setText(node,block.text);surface.append(node);
            }
            else if (block.type === 'table') surface.append(createTable(block.rows));
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
            else if (!event.shiftKey) {
                event.preventDefault();
                const row = table.insertRow();
                for (let column = 0; column < table.rows[0].cells.length; column++) row.append(createCell());
                caret(row.cells[0]);
                sync();
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
            const hasContent = collect().some(block => ['text','heading','quote'].includes(block.type) ? block.text.trim() : block.type==='list' ? block.items.some(item=>item.trim()) : block.type==='table' ? block.rows.some(row=>row.some(cell=>cell.trim())) : false);
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
