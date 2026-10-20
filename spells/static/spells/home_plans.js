(() => {
    document.querySelectorAll('[data-toggle-plan-form]').forEach(button=>{
        const form=document.getElementById(button.getAttribute('aria-controls'));
        if(!form)return;
        form.hidden=form.dataset.hasErrors!=='true';
        button.setAttribute('aria-expanded',String(!form.hidden));
        button.addEventListener('click',()=>{
            form.hidden=!form.hidden;
            button.setAttribute('aria-expanded',String(!form.hidden));
            if(!form.hidden)form.querySelector('input[name="title"]')?.focus();
        });
    });
    document.querySelectorAll('[data-confirm-plan-delete]').forEach(form=>form.addEventListener('submit',event=>{
        if(!window.confirm('Удалить этот план или напоминание?'))event.preventDefault();
    }));
})();
