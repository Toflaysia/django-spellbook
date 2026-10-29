(() => {
    const root=document.querySelector('.character-detail');
    if(!root)return;
    const status=root.querySelector('[data-training-status]');
    const names={none:'Без владения',proficient:'Владение',expertise:'Компетентность',half:'Половина мастерства'};
    const symbols={none:'○',proficient:'●',expertise:'◎',half:'◐'};
    const signed=n=>n>=0?`+${n}`:String(n);
    let pending=false;
    function paint(checks){
        for(const group of ['skills','saves','passives']){
            for(const row of checks[group]){
                const node=root.querySelector(`[data-check-group="${group}"][data-check-key="${row.key}"]`);
                if(!node)continue;
                const formula=node.querySelector('[data-check-formula]');if(formula)formula.textContent=row.formula;
                const button=node.querySelector('.training-cycle');
                if(button){
                    button.dataset.training=row.training_value;
                    button.querySelector('span').textContent=symbols[row.training_value];
                    const prefix=group==='saves'?'Спасбросок ':'';
                    button.setAttribute('aria-label',`${prefix}${row.label}: ${names[row.training_value]}. Изменить владение`);
                    button.title=`${names[row.training_value]}. Нажми для переключения`;
                    const label=node.querySelector('[data-check-training]');if(label)label.textContent=names[row.training_value];
                    const roll=node.querySelector('[data-dice-expression]');
                    roll.textContent=signed(row.total);roll.dataset.diceExpression=row.dice;roll.title=row.formula;
                    roll.setAttribute('aria-label',`${prefix}${row.label}: бросить ${row.dice}`);
                }else{const total=node.querySelector('[data-check-total]');if(total)total.textContent=row.total;}
            }
        }
    }
    root.addEventListener('click',async event=>{
        const button=event.target.closest('.training-cycle');
        if(!button||pending)return;
        const row=button.closest('[data-check-group]'),group=row.dataset.checkGroup;
        const cycle=group==='saves'?['none','proficient']:['none','proficient','expertise','half'];
        const next=cycle[(cycle.indexOf(button.dataset.training)+1)%cycle.length];
        const body=new FormData();body.set('action','training');body.set('group',group);body.set('key',row.dataset.checkKey);body.set('training',next);
        body.set('csrfmiddlewaretoken',root.querySelector('[name=csrfmiddlewaretoken]').value);
        pending=true;root.querySelectorAll('.training-cycle').forEach(b=>b.setAttribute('aria-disabled','true'));
        status.textContent='Сохраняю владение…';
        try{
            const response=await fetch(root.dataset.resourceUrl,{method:'POST',body});
            const data=await response.json();if(!response.ok)throw new Error(data.error||'Не удалось сохранить владение.');
            paint(data.checks);status.textContent='Владение сохранено.';
        }catch(error){status.textContent='Не удалось сохранить владение. Повтори нажатие.';}
        finally{pending=false;root.querySelectorAll('.training-cycle').forEach(b=>b.removeAttribute('aria-disabled'));}
    });
    root.addEventListener('submit',async event=>{
        const form=event.target.closest('.skill-bonus-form');
        if(!form)return;
        event.preventDefault();
        if(pending||!form.reportValidity())return;
        const body=new FormData(form);
        body.set('action','check_bonus');body.set('group',form.dataset.group);body.set('key',form.dataset.key);
        const submit=form.querySelector('button[type=submit]');
        pending=true;submit.disabled=true;
        root.querySelectorAll('.training-cycle').forEach(b=>b.setAttribute('aria-disabled','true'));
        status.textContent='Сохраняю бонус…';
        try{
            const response=await fetch(root.dataset.resourceUrl,{method:'POST',body});
            const data=await response.json();if(!response.ok)throw new Error(data.error||'Не удалось сохранить бонус.');
            paint(data.checks);status.textContent='Бонус сохранён.';
        }catch(error){status.textContent='Не удалось сохранить бонус. Проверь значение и повтори попытку.';}
        finally{pending=false;submit.disabled=false;root.querySelectorAll('.training-cycle').forEach(b=>b.removeAttribute('aria-disabled'));}
    });
})();
