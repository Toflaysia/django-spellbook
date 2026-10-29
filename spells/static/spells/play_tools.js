function initPlayTools() {
    'use strict';
    let config=document.querySelector('[data-play-tools]');
    if(!config){
        const source=document.querySelector('textarea[data-spell-search-url]');
        if(!source)return;
        config=document.createElement('div');
        config.dataset.playTools='';config.dataset.searchUrl=source.dataset.spellSearchUrl;config.dataset.previewUrl=source.dataset.spellPreviewUrl;config.dataset.catalogSearchUrl=source.dataset.catalogSearchUrl;config.dataset.catalogPreviewUrl=source.dataset.catalogPreviewUrl;
        config.innerHTML='<dialog id="spell-preview-dialog" class="play-dialog" aria-label="Просмотр заклинания"><button type="button" class="dialog-close" data-close-dialog aria-label="Закрыть">×</button><div data-preview-body aria-live="polite"></div></dialog><dialog id="spell-picker-dialog" class="play-dialog" aria-label="Ссылка на заклинание"><button type="button" class="dialog-close" data-close-dialog aria-label="Закрыть">×</button><h2>Ссылка на заклинание</h2><label>Название заклинания <input type="search" autocomplete="off"></label><div data-spell-results role="status"></div></dialog>';
        document.body.append(config);
    }
    if(config.dataset.ready)return;
    config.dataset.ready='true';
    const preview=document.getElementById('spell-preview-dialog');
    const body=preview.querySelector('[data-preview-body]');
    let previewRequest=null;
    const back=document.createElement('button');back.type='button';back.className='preview-back';back.textContent='← Назад';back.hidden=true;
    preview.querySelector('[data-preview-back]')?.remove();preview.insertBefore(back,body);
    const history=[];
    function returnNotices(){
        const notices=preview.querySelector('.dice-notifications');
        if(notices)document.body.append(notices);
    }
    preview.querySelector('[data-close-dialog]').addEventListener('click',()=>preview.close());
    preview.addEventListener('close',()=>{previewRequest?.abort();history.length=0;back.hidden=true;returnNotices();});
    back.addEventListener('click',()=>{
        previewRequest?.abort();const previous=history.pop();
        if(previous){body.innerHTML=previous.html;preview.scrollTop=previous.scroll;}
        body.removeAttribute('aria-busy');back.hidden=!history.length;
    });
    document.addEventListener('click',async event=>{
        const link=event.target.closest('[data-spell-id], [data-catalog-kind][data-catalog-id]');
        if(!link||link.closest('.description-surface'))return;
        event.preventDefault();
        previewRequest?.abort();const request=new AbortController();previewRequest=request;
        if(preview.open){
            if(body.getAttribute('aria-busy')!=='true')history.push({html:body.innerHTML,scroll:preview.scrollTop});
        }else{history.length=0;preview.showModal();}
        back.hidden=!history.length;
        body.textContent='Загружаю запись…';body.setAttribute('aria-busy','true');preview.scrollTop=0;
        try{
            let url;
            if(link.dataset.spellId)url=config.dataset.previewUrl.replace('/0/','/'+link.dataset.spellId+'/');
            else url=config.dataset.catalogPreviewUrl.replace('/schools/','/'+link.dataset.catalogKind+'/').replace('/0/','/'+link.dataset.catalogId+'/');
            const response=await fetch(url,{signal:request.signal});
            if(!response.ok)throw Error('Запись удалена или недоступна для твоего аккаунта.');
            const html=await response.text();
            if(previewRequest===request&&!request.signal.aborted)body.innerHTML=html;
        }catch(error){if(error.name!=='AbortError'&&previewRequest===request)body.textContent=error.message;}
        finally{if(previewRequest===request)body.removeAttribute('aria-busy');}
    });
    const picker=document.getElementById('spell-picker-dialog');
    const search=picker.querySelector('input');
    const results=picker.querySelector('[data-spell-results]');
    let pickerResolve=null,pickerRequest=null,timer=null,opener=null,pickerKind='spell';
    picker.querySelector('[data-close-dialog]').addEventListener('click',()=>picker.close());
    picker.addEventListener('close',()=>{
        pickerRequest?.abort();clearTimeout(timer);
        pickerResolve?.(null);pickerResolve=null;
        opener?.focus();
    });
    async function loadSpells(){
        pickerRequest?.abort();const request=new AbortController();pickerRequest=request;
        results.textContent='Поиск…';
        try{
            const url=new URL(pickerKind==='spell'?config.dataset.searchUrl:config.dataset.catalogSearchUrl.replace('/schools/','/'+pickerKind+'/'),location.origin);url.searchParams.set('search',search.value);
            const response=await fetch(url,{signal:request.signal});
            if(!response.ok)throw Error('Не удалось загрузить заклинания.');
            const data=await response.json();if(request.signal.aborted||pickerRequest!==request)return;results.replaceChildren();
            const items=pickerKind==='spell'?data.spells:data.items;
            for(const spell of items){
                const button=document.createElement('button');button.type='button';button.className='spell-picker-item';
                button.textContent=pickerKind==='spell'?`${spell.name} · ${spell.level===0?'заговор':'ур. '+spell.level}`:spell.name;
                button.addEventListener('click',()=>{
                    const resolve=pickerResolve;pickerResolve=null;resolve?.(spell);picker.close();
                });results.append(button);
            }
            if(!items.length)results.textContent='Ничего не найдено.';
        }catch(error){if(error.name!=='AbortError'&&pickerRequest===request)results.textContent=error.message;}
    }
    window.Spellbook=window.Spellbook||{};
    function pickObject(kind,title){return new Promise(resolve=>{
        opener=document.activeElement;pickerResolve=resolve;pickerKind=kind;
        picker.querySelector('h2').textContent=title;
        picker.setAttribute('aria-label',title);
        search.setAttribute('aria-label','Поиск: '+title);search.placeholder='Начни вводить название';
        const label=picker.querySelector('label');
        if(label&&!label.contains(search))label.textContent='Название';
        const hint=picker.querySelector('.play-muted');
        if(hint)hint.textContent=(kind==='effects'||kind==='conditions')?'Записи справочника «Состояния». Показаны первые 30 совпадений.':kind==='spell'?'Официальные, публичные авторские и твои приватные заклинания. Показаны первые 30 совпадений.':'Показаны первые 30 совпадений.';
        search.value='';picker.showModal();search.focus();loadSpells();
    });}
    window.Spellbook.pickSpell=()=>pickObject('spell','Ссылка на заклинание');
    window.Spellbook.pickCatalog=(kind)=>pickObject(kind,kind==='damage-types'?'Тип урона':kind==='traits'?'Черта':kind==='schools'?'Школа магии':'Состояние');
    search.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(loadSpells,200);});
    const labelDialog=document.createElement('dialog');
    labelDialog.className='play-dialog';labelDialog.setAttribute('aria-label','Текст ссылки');
    labelDialog.innerHTML='<h2>Текст ссылки</h2><form><label style="display:grid;gap:8px">Как написать ссылку в описании<input name="label" required maxlength="500" autocomplete="off"></label><p class="play-muted">Можно изменить падеж или написать своё название. Ссылка продолжит открывать выбранную запись.</p><button type="submit">Вставить</button> <button type="button" data-label-cancel>Отмена</button></form>';
    document.body.append(labelDialog);
    const labelInput=labelDialog.querySelector('input'),labelForm=labelDialog.querySelector('form');
    let labelResolve=null,labelOpener=null;
    function finishLabel(value){const resolve=labelResolve;labelResolve=null;labelDialog.close();resolve?.(value);}
    labelForm.addEventListener('submit',event=>{event.preventDefault();const value=labelInput.value.trim();if(value)finishLabel(value);else labelInput.focus();});
    labelDialog.querySelector('[data-label-cancel]').addEventListener('click',()=>finishLabel(null));
    labelDialog.addEventListener('close',()=>{const resolve=labelResolve;labelResolve=null;resolve?.(null);labelOpener?.focus();});
    window.Spellbook.pickLinkLabel=(value,editing=false)=>new Promise(resolve=>{
        labelOpener=document.activeElement;labelResolve=resolve;labelInput.value=value;
        labelForm.querySelector('[type="submit"]').textContent=editing?'Сохранить':'Вставить';
        labelDialog.showModal();labelInput.focus();labelInput.select();
    });

    // Rejection sampling avoids modulo bias for dice of every size.
    function randomDie(sides){
        const ceiling=Math.floor(4294967296/sides)*sides;
        const buffer=new Uint32Array(1);do{crypto.getRandomValues(buffer);}while(buffer[0]>=ceiling);
        return buffer[0]%sides+1;
    }
    function roll(expression,validateOnly=false){
        const text=expression.toLowerCase().replace(/\s/g,'');
        if(!text||text.length>120||!/^[-+]?(?:\d*d\d+(?:k[hl]\d+)?|\d+)(?:[-+](?:\d*d\d+(?:k[hl]\d+)?|\d+))*$/.test(text))throw Error('Пример: 2d6+3 или 2d20kh1.');
        let total=0,number=0;const details=[];
        for(const term of text.match(/[+-]?[^+-]+/g)){
            const sign=term[0]==='-'?-1:1;
            const raw=term.replace(/^[+-]/,'');
            const match=raw.match(/^(\d*)d(\d+)(?:k([hl])(\d+))?$/);
            if(!match){const modifier=Number(raw);if(!Number.isSafeInteger(modifier)||modifier>1e6)throw Error('Слишком большой модификатор.');total+=sign*modifier;details.push(`${sign<0?'−':'+'}${modifier}`);continue;}
            const count=Number(match[1]||1),sides=Number(match[2]),keep=match[4]?Number(match[4]):count;
            number+=count;
            if(count<1||count>100||number>200||sides<2||sides>1000||keep<1||keep>count)throw Error('От 1 до 100 кубиков в группе, не более 200 за бросок; грани от 2 до 1000.');
            const values=Array.from({length:count},()=>validateOnly?1:randomDie(sides));
            const selected=match[3]?[...values].sort((a,b)=>match[3]==='h'?b-a:a-b).slice(0,keep):values;
            const sum=selected.reduce((a,b)=>a+b,0);total+=sign*sum;
            details.push(`${sign<0?'−':'+'}${raw}: [${values.join(', ')}]${match[3]?'; оставлено '+selected.join(', '):''}`);
        }
        return {total,details:details.join(' · ')};
    }
    window.Spellbook.roll=roll;
    // A separate insertion dialog keeps validation errors near the formula.
    const diceDialog=document.createElement('dialog');diceDialog.className='play-dialog';diceDialog.setAttribute('aria-label','Вставить бросок кубиков');
    diceDialog.innerHTML='<button type="button" class="dialog-close" aria-label="Закрыть">×</button><h2>Бросок кубиков</h2><form><label for="inline-dice-expression">Формула броска</label><input id="inline-dice-expression" class="inline-dice-input" name="expression" maxlength="120" required placeholder="2d6+3"><p class="play-muted">Например: 2d6+3, 1d20 или 2d20kh1+5.</p><p role="alert" data-dice-error></p><button type="submit">Вставить</button></form>';
    document.body.append(diceDialog);
    let resolveDice=null;
    diceDialog.querySelector('.dialog-close').addEventListener('click',()=>diceDialog.close());
    diceDialog.addEventListener('close',()=>{resolveDice?.(null);resolveDice=null;});
    diceDialog.querySelector('form').addEventListener('submit',event=>{
        event.preventDefault();const input=diceDialog.querySelector('input');
        try{
            if(!/d\d/i.test(input.value))throw Error('Укажи кубик, например 2d6+3.');
            roll(input.value,true);
            const resolve=resolveDice;resolveDice=null;resolve?.(input.value.toLowerCase().replace(/\s/g,''));diceDialog.close();
        }catch(error){diceDialog.querySelector('[data-dice-error]').textContent=error.message;input.focus();}
    });
    window.Spellbook.pickDice=()=>new Promise(resolve=>{
        resolveDice=resolve;diceDialog.querySelector('input').value='';diceDialog.querySelector('[data-dice-error]').textContent='';diceDialog.showModal();diceDialog.querySelector('input').focus();
    });
    let notices=document.querySelector('.dice-notifications');
    if(!notices){notices=document.createElement('div');notices.className='dice-notifications';notices.setAttribute('aria-live','polite');notices.setAttribute('aria-label','Уведомления о бросках');document.body.append(notices);}
    if(typeof notices.showPopover==='function')notices.setAttribute('popover','manual');
    function animateDice(){
        const graphic=document.querySelector('.dice-toggle svg');
        if(!graphic||typeof graphic.animate!=='function'||matchMedia('(prefers-reduced-motion: reduce)').matches)return;
        graphic.getAnimations().forEach(animation=>animation.cancel());
        graphic.animate([
            {transform:'rotate(0deg) scale(1)'},
            {transform:'rotate(-18deg) scale(.9)',offset:.15},
            {transform:'rotate(165deg) scale(1.08)',offset:.55},
            {transform:'rotate(360deg) scale(1)'}
        ],{duration:650,easing:'ease-out'});
    }
    function showRoll(expression){
        const notice=document.createElement('article');notice.className='dice-notification';
        const title=document.createElement('strong'),details=document.createElement('p');
        let success=true;
        try{const value=roll(expression);animateDice();title.textContent=`${expression} = ${value.total}`;details.textContent=value.details;}
        catch(error){success=false;title.textContent='Не удалось бросить кубики';details.textContent=error.message;}
        const dismiss=document.createElement('button');dismiss.type='button';dismiss.className='dice-notification-close';dismiss.textContent='×';dismiss.setAttribute('aria-label','Закрыть уведомление о броске');
        let fadeTimeout,removeTimeout;
        function removeNotice(){
            clearTimeout(fadeTimeout);clearTimeout(removeTimeout);
            notice.remove();
            if(!notices.children.length)notices.hidePopover?.();
        }
        fadeTimeout=setTimeout(()=>notice.classList.add('is-fading'),11000);
        removeTimeout=setTimeout(removeNotice,15000);
        dismiss.addEventListener('click',removeNotice);
        notice.append(title,details,dismiss);
        const dialog=document.querySelector('dialog[open]');
        (notices.hasAttribute('popover')?document.body:(dialog||document.body)).append(notices);notices.append(notice);notices.showPopover?.();
        return success;
    }
    document.addEventListener('close',()=>{if(!document.querySelector('dialog[open]'))document.body.append(notices);},true);
    document.addEventListener('click',event=>{
        const button=event.target.closest('[data-dice-expression]');
        if(!button||button.closest('.description-surface'))return;
        event.preventDefault();showRoll(button.dataset.diceExpression);
    });
    window.Spellbook.showRoll=showRoll;
    const widget=document.querySelector('.dice-widget');if(!widget)return;
    const toggle=widget.querySelector('.dice-toggle'),panel=widget.querySelector('.dice-panel');
    const form=widget.querySelector('form'),input=form.elements.expression,result=widget.querySelector('.dice-result');
    function close(){panel.hidden=true;toggle.setAttribute('aria-expanded','false');toggle.focus();}
    toggle.addEventListener('click',()=>{animateDice();panel.hidden=!panel.hidden;toggle.setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden)input.focus();});
    widget.querySelector('[data-dice-close]').addEventListener('click',close);
    widget.addEventListener('keydown',e=>{if(e.key==='Escape')close();});
    form.addEventListener('submit',e=>{e.preventDefault();showRoll(input.value);});
    widget.querySelectorAll('[data-die]').forEach(button=>button.addEventListener('click',()=>{input.value='1d'+button.dataset.die;showRoll(input.value);}));
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initPlayTools,{once:true});
else initPlayTools();
