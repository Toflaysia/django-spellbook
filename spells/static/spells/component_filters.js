(() => {
    const filters=[...document.querySelectorAll('[data-component-filter]')];
    filters.forEach(filter=>{
        const summary=filter.querySelector('[data-component-summary]');
        const sync=()=>{
            const selected=[...filter.querySelectorAll('input:checked')].map(input=>input.closest('label').textContent.trim());
            summary.textContent=selected.join(', ') || 'Любые компоненты';
        };
        filter.addEventListener('change',sync);
        filter.addEventListener('toggle',()=>{
            if(filter.open)filters.forEach(other=>{if(other!==filter)other.open=false;});
        });
        filter.addEventListener('keydown',event=>{
            if(event.key==='Escape'){
                filter.open=false;
                filter.querySelector('summary').focus();
            }
        });
        sync();
    });
    document.addEventListener('click',event=>filters.forEach(filter=>{
        if(!filter.contains(event.target))filter.open=false;
    }));
})();
