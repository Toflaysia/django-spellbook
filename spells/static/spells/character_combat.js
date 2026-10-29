(() => {
    const root=document.querySelector('[data-combat-url]'),character=document.querySelector('.character-detail');if(!root)return;
    let state=JSON.parse(document.getElementById('character-combat-state').textContent),busy=false,searchController;
    const make=(tag,text,attrs={})=>{const n=document.createElement(tag);if(text!==null)n.textContent=text;Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));return n;};
    const button=(text,action,attrs={})=>make('button',text,{type:'button','data-combat-action':action,...attrs});
    const status=(text,error=false)=>root.querySelectorAll('[data-combat-status]').forEach(n=>{n.textContent=text;n.classList.toggle('combat-error',error);});
    const catalog=JSON.parse(document.getElementById('condition-choice-catalog').textContent),editor=root.querySelector('#condition-editor'),conditionForm=editor.querySelector('form');
    let conditionTrigger=null;
    // Состояния и концентрация выводятся из одного серверного состояния.
    function paint(){
        const active=Boolean(state.concentration.name);
        const conditions=root.querySelector('[data-condition-list]');conditions.replaceChildren();
        if(!state.conditions.length){const empty=make('div',null,{class:'condition-empty'});empty.append(make('strong','Нет активных состояний'),make('p','Нажми «Добавить состояние», если персонаж отравлен, испуган или находится под другим состоянием.'));conditions.append(empty);}
        state.conditions.forEach(c=>{
            const card=make('article',null,{class:'condition-card'}),head=make('div',null,{class:'condition-heading'});
            head.append(make('h3',c.name));card.append(head);
            if(c.note)card.append(make('p',c.note,{class:'condition-note'}));
            if(c.incapacitates)card.append(make('p','Прерывает концентрацию',{class:'combat-warning'}));
            const details=make('details',null,{class:'condition-card-description'});details.append(make('summary','Описание'),make('p',c.description||'В справочнике пока нет описания.',{class:'condition-description'}),make('a','Открыть в справочнике',{href:c.url,target:'_blank',rel:'noopener'}));card.append(details);
            const actions=make('div',null,{class:'condition-card-actions'});actions.append(make('button','Изменить',{type:'button','data-condition-edit':c.id,'aria-label':`Изменить состояние: ${c.name}`,class:'btn-secondary'}),button('Снять','condition_remove',{'data-condition-row-id':c.id,'aria-label':`Снять состояние: ${c.name}`,class:'btn-secondary'}));card.append(actions);conditions.append(card);
        });
        root.querySelector('[data-condition-count]').textContent=state.conditions.length?`Активных состояний: ${state.conditions.length}`:'Отмечай состояния и снимай их после окончания действия.';
        const current=root.querySelector('[data-concentration-current]');current.replaceChildren();
        if(active){const p=make('p',null,{class:'concentration-active'});p.append(make('strong','Концентрация: '),state.concentration.url?make('a',state.concentration.name,{href:state.concentration.url,target:'_blank',rel:'noopener'}):make('span',state.concentration.name));current.append(p,button('Прекратить концентрацию','concentration_end'));}
        else current.append(make('p','Нет активной концентрации.',{class:'combat-muted'}));
        root.querySelector('[data-concentration-replace]').hidden=!active;
        root.querySelector('[name=replace]').required=active;
        root.querySelector('[data-manual-check-section]').hidden=!active;
        const section=root.querySelector('[data-concentration-checks-section]');section.hidden=!state.checks.length;
        root.querySelector('[data-concentration-save]').textContent=`Спасбросок Телосложения: ${state.save_bonus>=0?'+':''}${state.save_bonus}. ${state.save_formula}`;
        const checks=root.querySelector('[data-concentration-checks]');checks.replaceChildren();
        state.checks.forEach(c=>{
            const form=make('form',null,{'data-combat-form':'concentration_check',class:'concentration-check'});
            form.append(make('strong',c.damage?`Урон ${c.damage} · СЛ ${c.dc}`:`Проверка мастера · СЛ ${c.dc}`),make('input',null,{type:'hidden',name:'check_id',value:c.id}));
            const label=make('label','Режим броска'),select=make('select',null,{name:'mode'});for(const [value,text] of [['normal','Обычный'],['advantage','Преимущество'],['disadvantage','Помеха']])select.append(make('option',text,{value}));label.append(select);form.append(label);
            const actions=make('div',null,{class:'concentration-check-actions'});actions.append(make('button','Бросить спасбросок',{type:'submit','data-roll-check':''}));form.append(actions);checks.append(form);
        });
        const quick=character.querySelector('[data-combat-quick]');quick.replaceChildren();quick.hidden=!active;
        if(active)quick.append(make('button',`Концентрация: ${state.concentration.name}${state.checks.length?` · проверок: ${state.checks.length}`:''}`,{type:'button','data-open-concentration':'',class:'combat-chip'}));
        character.querySelectorAll('#hp-calculator [data-open-concentration]').forEach(b=>b.hidden=!state.checks.length);
    }
    character.addEventListener('spellbook:combat-updated',event=>{if(event.detail.revision>=state.revision){state=event.detail;paint();}});
    character.addEventListener('click',event=>{
        if(!event.target.closest('[data-open-concentration]'))return;
        character.querySelectorAll('dialog[open]').forEach(d=>d.close());character.querySelector('#tab-spellbooks').click();
        const target=root.querySelector('#character-combat');target.open=true;target.scrollIntoView({block:'start',behavior:'smooth'});
    });
    function previewCondition(id){
        const selected=catalog.find(c=>String(c.id)===String(id)),preview=editor.querySelector('[data-condition-preview]');
        conditionForm.elements.condition_id.value=selected?selected.id:'';preview.hidden=!selected;
        editor.querySelector('[data-condition-submit]').disabled=!selected;
        if(selected){preview.querySelector('h3').textContent=selected.name;preview.querySelector('p').textContent=selected.description||'В справочнике пока нет описания.';}
    }
    function filterChoices(){
        const query=editor.querySelector('[data-condition-search]').value.trim().toLocaleLowerCase('ru');let visible=0;
        editor.querySelectorAll('.condition-choice').forEach(label=>{label.hidden=!label.dataset.name.includes(query);if(!label.hidden)visible++;});
        editor.querySelector('[data-condition-no-results]').hidden=visible>0;
    }
    function openCondition(row,trigger){
        if(busy)return;conditionTrigger=trigger;conditionForm.reset();status('');editor.querySelector('[data-condition-search]').value='';
        editor.querySelector('[data-condition-picker]').hidden=Boolean(row);editor.querySelector('.condition-extra').open=Boolean(row);
        editor.querySelector('#condition-editor-title').textContent=row?'Изменить состояние':'Добавить состояние';
        editor.querySelector('[data-condition-submit]').textContent=row?'Сохранить изменения':'Добавить состояние';
        const options=editor.querySelector('[data-condition-options]');options.replaceChildren();
        catalog.forEach(c=>{const active=state.conditions.some(item=>item.condition_id===c.id),label=make('label',null,{class:'condition-choice','data-name':c.name.toLocaleLowerCase('ru')});
            const radio=make('input',null,{type:'radio',name:'condition_choice',value:c.id});radio.disabled=active;label.classList.toggle('condition-choice-active',active);
            label.append(radio,make('span',c.name));if(active)label.append(make('small','Уже добавлено'));options.append(label);
        });
        if(!catalog.length){editor.querySelector('[data-condition-no-results]').textContent='В справочнике пока нет состояний. Добавь их в раздел «Состояния».';editor.querySelector('[data-condition-no-results]').hidden=false;}
        else{editor.querySelector('[data-condition-no-results]').textContent='Ничего не найдено. Попробуй другое название.';filterChoices();}
        previewCondition(row?.condition_id);
        if(row){conditionForm.elements.note.value=row.note;conditionForm.elements.incapacitates.checked=row.incapacitates;}
        editor.showModal();editor.querySelector(row?'[name=note]':'[data-condition-search]').focus();
    }
    editor.addEventListener('change',event=>{if(event.target.name==='condition_choice')previewCondition(event.target.value);});
    editor.querySelector('[data-condition-search]').addEventListener('input',filterChoices);
    editor.addEventListener('close',()=>{if(conditionTrigger?.isConnected)conditionTrigger.focus();else root.querySelector('[data-condition-add]').focus();});
    async function send(body){
        if(busy)return false;busy=true;root.setAttribute('aria-busy','true');body.set('revision',state.revision);body.set('csrfmiddlewaretoken',root.querySelector('[name=csrfmiddlewaretoken]').value);
        const buttons=[...root.querySelectorAll('button')];buttons.forEach(b=>{b.dataset.wasDisabled=String(b.disabled);b.disabled=true;});
        try{
            const response=await fetch(root.dataset.combatUrl,{method:'POST',body});if(!response.headers.get('content-type')?.includes('application/json'))throw Error('Не удалось получить ответ. Обнови страницу перед повторной попыткой.');
            const data=await response.json();if(data.combat&&data.combat.revision>=state.revision)state=data.combat;
            if(!response.ok)throw Error(data.error||'Не удалось сохранить.');status(data.message);return true;
        }catch(error){status(error.message,true);return false;}
        finally{busy=false;root.removeAttribute('aria-busy');buttons.forEach(b=>b.disabled=b.dataset.wasDisabled==='true');paint();}
    }
    root.addEventListener('click',async event=>{
        const add=event.target.closest('[data-condition-add]');if(add){openCondition(null,add);return;}
        const edit=event.target.closest('[data-condition-edit]');if(edit){const row=state.conditions.find(c=>String(c.id)===edit.dataset.conditionEdit);if(row)openCondition(row,edit);return;}
        if(event.target.closest('[data-condition-cancel]')){editor.close();return;}
        const b=event.target.closest('[data-combat-action]');if(!b)return;
        const body=new FormData();body.set('action',b.dataset.combatAction);if(b.dataset.conditionRowId)body.set('condition_row_id',b.dataset.conditionRowId);await send(body);
    });
    root.addEventListener('submit',async event=>{
        const form=event.target.closest('[data-combat-form]');if(!form)return;event.preventDefault();if(busy)return;
        const body=new FormData(form);let action=form.dataset.combatForm;
        // В интерфейсе оставлен серверный бросок: результат не берётся из кнопки «успех».
        if(action==='concentration_check')action='concentration_roll';
        if(action==='condition_add'&&!body.get('condition_id')){status('Сначала выбери состояние.',true);return;}
        body.set('action',action);
        if(await send(body)){if(['condition_add','concentration_start'].includes(action))form.reset();if(action==='condition_add')editor.close();if(action==='concentration_start')root.querySelector('[data-concentration-editor]').open=false;}
    });
    async function search(){
        searchController?.abort();searchController=new AbortController();const searchStatus=root.querySelector('[data-spell-search-status]'),select=root.querySelector('[name=spell_id]');
        searchStatus.textContent='Ищу заклинания…';
        try{
            const url=new URL(root.dataset.spellSearchUrl,location.origin);url.searchParams.set('search',root.querySelector('[name=search]').value);
            const response=await fetch(url,{signal:searchController.signal});if(!response.ok)throw Error('Не удалось найти заклинания. Обнови страницу и проверь вход в аккаунт.');
            const data=await response.json();select.replaceChildren(make('option','Выбери заклинание',{value:''}));data.spells.forEach(s=>select.append(make('option',s.name,{value:s.id})));
            searchStatus.textContent=data.spells.length?(data.spells.length===30?'Показаны первые 30 записей. Уточни название для поиска.':''):'Заклинания с концентрацией не найдены.';
        }catch(error){if(error.name!=='AbortError')searchStatus.textContent=error.message;}
    }
    root.querySelector('[data-concentration-search]').addEventListener('submit',event=>{event.preventDefault();search();});
    paint();search();
})();
