(() => {
    const root=document.querySelector('.character-rests');
    if(!root)return;
    let state=JSON.parse(document.getElementById('character-rest-state').textContent),busy=false;
    const make=(tag,text,attrs={})=>{
        const node=document.createElement(tag);if(text!==null)node.textContent=text;
        Object.entries(attrs).forEach(([k,v])=>node.setAttribute(k,v));return node;
    };
    const button=(text,action,extra={})=>{const node=make('button',text,{type:'button','data-rest-action':action,...extra});return node;};
    const status=(text,error=false)=>root.querySelectorAll('[data-rest-status]').forEach(n=>{n.textContent=text;n.classList.toggle('rest-error',error);});
    function paint(){
        const summary=root.querySelector('[data-dice-summary]');summary.replaceChildren();
        state.dice.forEach(d=>summary.append(make('span',`d${d.die}: ${d.available} / ${d.maximum}`,{class:'rest-chip',title:'Доступные кости хитов / максимум'})));
        const spend=root.querySelector('[data-spend-dice]');spend.replaceChildren();
        state.dice.forEach(d=>{const row=make('div',null,{class:'rest-die-row'});row.append(make('span',`d${d.die} · осталось ${d.available} / ${d.maximum}`));const b=button(`Потратить d${d.die}`,'spend_hit_die',{'data-die':d.die});b.disabled=!d.available;row.append(b);spend.append(row);});
        root.querySelector('[data-recovery-budget]').textContent=state.recovery_budget;
        const recovery=root.querySelector('[data-recover-dice]');recovery.replaceChildren();
        state.dice.forEach(d=>{
            const row=make('div',null,{class:'rest-recovery-row'}),label=make('label',`Восстановить d${d.die}`,{for:`recover-die-${d.die}`});
            label.append(make('small',`Потрачено: ${d.spent} из ${d.maximum}`));
            const controls=make('div',null,{class:'rest-number-control'}),input=make('input',null,{type:'number',id:`recover-die-${d.die}`,name:`recover_${d.die}`,min:0,max:d.spent,step:1,inputmode:'numeric',value:d.recover,required:''});
            const minus=make('button','−',{type:'button','data-recovery-step':'-1','aria-label':`Уменьшить восстановление d${d.die}`}),plus=make('button','+',{type:'button','data-recovery-step':'1','aria-label':`Увеличить восстановление d${d.die}`});
            controls.append(minus,input,plus);row.append(label,controls);recovery.append(row);
        });
        recoveryTotal();
        const resources=root.querySelector('[data-resource-list]');resources.replaceChildren();
        if(!state.resources.length)resources.append(make('p','Добавь способности с ограниченным числом использований.',{class:'rest-hint'}));
        state.resources.forEach(r=>{const card=make('div',null,{class:'rest-resource'}),info=make('div',null);info.append(make('strong',r.name),make('small',r.refresh_label));const controls=make('div',null,{class:'rest-counter'});
            const minus=button('−','resource_change',{'data-resource-id':r.id,'data-operation':'spend','aria-label':`Потратить: ${r.name}`});minus.disabled=r.current===0;
            const plus=button('+','resource_change',{'data-resource-id':r.id,'data-operation':'restore','aria-label':`Восстановить: ${r.name}`});plus.disabled=r.current===r.maximum;
            controls.append(minus,make('span',`${r.current} / ${r.maximum}`),plus);card.append(info,controls);
            const remove=button('Удалить','resource_delete',{'data-resource-id':r.id,class:'rest-remove','data-resource-name':r.name});card.append(remove);resources.append(card);
        });
        root.querySelectorAll('[data-rest-books]').forEach(container=>{
            const checked=new Set([...container.querySelectorAll('input:checked')].map(n=>Number(n.value))),initial=!container.dataset.initialized;
            container.replaceChildren();state.books.forEach(b=>{const label=make('label',null,{class:'rest-check'}),input=make('input',null,{type:'checkbox',name:'book_ids',value:b.id});input.checked=initial?b.active:checked.has(b.id);label.append(input,document.createTextNode(b.name));container.append(label);});
            if(!state.books.length)container.append(make('p','У персонажа пока нет спеллбуков.',{class:'rest-hint'}));container.dataset.initialized='true';
        });
    }
    function recoveryTotal(){
        const inputs=[...root.querySelectorAll('[data-recover-dice] input')],total=inputs.reduce((sum,input)=>sum+(Number(input.value)||0),0);
        const output=root.querySelector('[data-recovery-total]');output.textContent=`Выбрано: ${total} из ${state.recovery_budget}`;
        output.classList.toggle('rest-error',total>state.recovery_budget);
        if(inputs[0])inputs[0].setCustomValidity(total>state.recovery_budget?`Можно восстановить не больше ${state.recovery_budget} костей хитов.`:'');
        inputs.forEach(input=>{const controls=input.closest('.rest-number-control');controls.querySelector('[data-recovery-step="-1"]').disabled=Number(input.value)<=0;controls.querySelector('[data-recovery-step="1"]').disabled=Number(input.value)>=Number(input.max);});
    }
    root.addEventListener('input',event=>{if(event.target.matches('[data-recover-dice] input'))recoveryTotal();});
    async function send(body){
        if(busy)return false;busy=true;root.setAttribute('aria-busy','true');
        body.set('revision',state.revision);body.set('csrfmiddlewaretoken',root.querySelector('[name=csrfmiddlewaretoken]').value);
        root.querySelectorAll('button').forEach(b=>{b.dataset.wasDisabled=String(b.disabled);b.disabled=true;});
        try{
            const response=await fetch(root.dataset.restUrl,{method:'POST',body});let data;
            try{data=await response.json();}catch{throw new Error('Не удалось получить ответ. Обнови страницу перед повторной попыткой.');}
            if(data.rest)state=data.rest;
            if(data.combat)document.querySelector('.character-detail').dispatchEvent(new CustomEvent('spellbook:combat-updated',{detail:data.combat}));
            if(data.health)document.querySelector('.character-detail').dispatchEvent(new CustomEvent('spellbook:rest-updated',{detail:data.health}));
            if(!response.ok)throw new Error(data.error||'Не удалось сохранить изменения.');
            status(data.message);return true;
        }catch(error){status(error.message,true);return false;}
        finally{busy=false;root.removeAttribute('aria-busy');root.querySelectorAll('button').forEach(b=>b.disabled=b.dataset.wasDisabled==='true');paint();}
    }
    root.addEventListener('click',async event=>{
        const step=event.target.closest('[data-recovery-step]');
        if(step){if(busy)return;const input=step.closest('.rest-number-control').querySelector('input');if(!input.value)input.value='0';if(step.dataset.recoveryStep==='1')input.stepUp();else input.stepDown();recoveryTotal();return;}
        const open=event.target.closest('[data-rest-open]');if(open){status('');root.querySelector(`#${open.dataset.restOpen}`).showModal();return;}
        const close=event.target.closest('[data-rest-close]');if(close){close.closest('dialog').close();return;}
        const b=event.target.closest('[data-rest-action]');if(!b||busy)return;
        if(b.dataset.restAction==='resource_delete'&&!confirm(`Удалить ресурс «${b.dataset.resourceName}»?`))return;
        const body=new FormData();body.set('action',b.dataset.restAction);
        for(const key of ['die','resourceId','operation'])if(b.dataset[key])body.set(key==='resourceId'?'resource_id':key,b.dataset[key]);
        await send(body);
    });
    root.addEventListener('submit',async event=>{
        const form=event.target.closest('[data-rest-form]');if(!form)return;event.preventDefault();if(busy)return;
        const body=new FormData(form);body.set('action',form.dataset.restForm);
        if(await send(body)){
            if(form.dataset.restForm==='resource_create'){form.reset();form.closest('details').open=false;}
            else{form.closest('dialog').close();}
        }
    });
    paint();
})();
