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
    document.querySelectorAll('.home-plan-form').forEach(form=>{
        const checkbox=form.querySelector('[data-email-reminder]');
        const date=form.querySelector('[data-reminder-date]');
        const input=form.querySelector('[data-reminder-time]');
        const dateRow=date?.closest('p');
        const timeRow=input?.closest('p');
        if(!checkbox || !date || !input || !dateRow || !timeRow)return;
        const schedule=document.createElement('div');
        schedule.className='home-plan-schedule';
        dateRow.before(schedule);
        schedule.append(dateRow,timeRow);
        const sync=()=>{
            const enabled=checkbox.checked && !checkbox.disabled;
            schedule.hidden=!enabled;
            [date,input].forEach(field=>{
                field.disabled=!enabled;
                field.required=enabled;
            });
        };
        checkbox.addEventListener('change',sync);
        sync();
    });
    document.querySelectorAll('[data-confirm-plan-delete]').forEach(form=>form.addEventListener('submit',event=>{
        if(!window.confirm('Удалить этот план или напоминание?'))event.preventDefault();
    }));
})();
