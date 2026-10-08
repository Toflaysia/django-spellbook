(() => {
    const form = document.getElementById('progression-form');
    if (!form) return;
    const source = form.querySelector('[name="columns"]');
    const grid = document.getElementById('progression-grid');
    const presets = JSON.parse(document.getElementById('progression-presets').textContent);
    const isSubclass = form.dataset.subclass === 'true';
    const add = document.getElementById('add-progression-column');
    let columns;
    try { columns = JSON.parse(source.value || '[]'); }
    catch { return; }
    if (!Array.isArray(columns)) return;
    const make = (tag, text) => {
        const node = document.createElement(tag);
        if (text !== undefined) node.textContent = text;
        return node;
    };
    function sync() { source.value = JSON.stringify(columns); }
    function control(text, label, action) {
        const button = make('button', text);
        button.type = 'button';
        button.title = label;
        button.setAttribute('aria-label', label);
        button.addEventListener('click', action);
        return button;
    }
    function render() {
        grid.replaceChildren();
        add.disabled = columns.length >= 24;
        if (!columns.length && isSubclass) {
            grid.append(make('p', 'Дополнительные столбцы пока не добавлены.'));
            sync();
            return;
        }
        const table = make('table');
        table.className = 'progression-grid';
        const head = make('thead');
        const headings = make('tr');
        if (isSubclass) headings.append(make('th', 'Уровень'));
        columns.forEach((column, index) => {
            const th = make('th');
            th.scope = 'col';
            const input = make('input');
            input.value = column.title;
            input.maxLength = 80;
            input.required = true;
            input.setAttribute('aria-label', `Название столбца ${index + 1}`);
            input.addEventListener('input', () => { column.title = input.value; sync(); });
            const actions = make('div');
            actions.className = 'progression-column-actions';
            const up = control('←', 'Переместить столбец влево', () => {
                [columns[index - 1], columns[index]] = [columns[index], columns[index - 1]];
                render();
            });
            up.disabled = index === 0;
            const down = control('→', 'Переместить столбец вправо', () => {
                [columns[index + 1], columns[index]] = [columns[index], columns[index + 1]];
                render();
            });
            down.disabled = index === columns.length - 1;
            actions.append(up, down);
            if (column.kind === 'text') actions.append(control('Удалить', `Удалить столбец ${column.title}`, () => {
                columns.splice(index, 1); render();
            }));
            th.append(input, actions);
            headings.append(th);
        });
        head.append(headings);
        const body = make('tbody');
        for (let level = 1; level <= 20; level++) {
            const row = make('tr');
            if (isSubclass) { const th = make('th', String(level)); th.scope = 'row'; row.append(th); }
            columns.forEach((column, index) => {
                const td = make('td');
                if (column.kind === 'text') {
                    const input = make('input');
                    input.value = column.values[level - 1];
                    input.maxLength = 200;
                    input.setAttribute('aria-label', `Уровень ${level}, столбец ${index + 1}`);
                    input.addEventListener('input', () => { column.values[level - 1] = input.value; sync(); });
                    td.append(input);
                } else {
                    td.textContent = column.kind === 'level' ? String(level)
                        : column.kind === 'proficiency' ? `+${2 + Math.floor((level - 1) / 4)}`
                        : 'Из справочника умений';
                }
                row.append(td);
            });
            body.append(row);
        }
        table.append(head, body);
        grid.append(table);
        sync();
    }
    add.addEventListener('click', () => {
        if (columns.length >= 24) return;
        const key = 'custom_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2);
        columns.push({key, kind: 'text', title: 'Новый столбец', values: Array(20).fill('')});
        render();
        grid.querySelectorAll('thead input')[columns.length - 1].focus();
    });
    document.getElementById('apply-progression-preset')?.addEventListener('click', () => {
        const kind = form.querySelector('[name="table_type"]').value;
        const next = JSON.parse(JSON.stringify(presets[kind]));
        const removed = columns.filter((column) => column.kind === 'text'
            && !next.some((item) => item.key === column.key));
        if (removed.some((column) => column.values.some((value) => value.trim()))
            && !window.confirm('В новом шаблоне нет некоторых заполненных столбцов. Убрать их из таблицы?')) return;
        next.forEach((column) => {
            const old = columns.find((item) => item.key === column.key && item.kind === column.kind);
            if (old && column.kind === 'text') column.values = [...old.values];
        });
        columns = next;
        render();
    });
    form.addEventListener('submit', sync);
    render();
})();
