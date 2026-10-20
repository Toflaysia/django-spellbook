(() => {
    const root=document.querySelector('.character-detail');
    if(!root) return;
    const activeForm=root.querySelector('[data-active-form]');
    if(activeForm){
        const checkbox=activeForm.elements.is_active;
        checkbox.addEventListener('change',async()=>{
            const chosen=checkbox.checked;checkbox.disabled=true;
            const status=activeForm.querySelector('[data-active-status]');
            try{
                const body=new FormData(activeForm);body.set('action','active');body.set('is_active',String(chosen));
                const response=await fetch(root.dataset.resourceUrl,{method:'POST',body});
                const data=await response.json();if(!response.ok)throw new Error(data.error||'Не удалось сохранить');
                status.textContent='Сохранено';
            }catch(error){checkbox.checked=!chosen;status.textContent=error.message;}
            finally{checkbox.disabled=false;}
        });
    }
    const tabs=[...root.querySelectorAll('[role="tab"]')];
    function activate(tab, update=true){
        tabs.forEach(t=>{t.setAttribute('aria-selected',String(t===tab));t.tabIndex=t===tab?0:-1;});
        root.querySelectorAll('[role="tabpanel"]').forEach(p=>{p.hidden=p.id!==tab.getAttribute('aria-controls');});
        if(update)history.replaceState(null,'',`#${tab.getAttribute('aria-controls')}`);
    }
    tabs.forEach((tab,index)=>{
        tab.addEventListener('click',()=>activate(tab));
        tab.addEventListener('keydown',e=>{
            let i;
            if(e.key==='ArrowRight')i=(index+1)%tabs.length;
            else if(e.key==='ArrowLeft')i=(index+tabs.length-1)%tabs.length;
            else if(e.key==='Home')i=0;
            else if(e.key==='End')i=tabs.length-1;
            else return;
            e.preventDefault();activate(tabs[i]);tabs[i].focus();
        });
    });
    const fromHash=()=>activate(tabs.find(t=>`#${t.getAttribute('aria-controls')}`===location.hash)||tabs[0],false);
    fromHash();window.addEventListener('hashchange',fromHash);
    root.querySelectorAll('[data-open-calculator]').forEach(button=>button.addEventListener('click',()=>{
        const dialog=document.getElementById(button.dataset.openCalculator);dialog.showModal();dialog.querySelector('input[name="amount"]').focus();
    }));
    root.querySelectorAll('[data-close-dialog]').forEach(button=>button.addEventListener('click',()=>button.closest('dialog').close()));
    function paint(data){
        root.querySelectorAll('[data-hp-current]').forEach(n=>{n.textContent=data.current;n.classList.toggle('hp-low',data.current*2<=data.maximum);});
        root.querySelectorAll('[data-hp-max]').forEach(n=>n.textContent=data.maximum);
        root.querySelectorAll('[data-hp-temp]').forEach(n=>{n.textContent=data.temporary;n.closest('.hp-temporary').hidden=Number(data.temporary)<=0;});
        root.querySelectorAll('[data-gold-total]').forEach(n=>n.textContent=data.gold_total);
        root.querySelectorAll('[data-coin]').forEach(n=>n.textContent=data.coins[n.dataset.coin]);
    }
    const coinNames={gold:'Золотые',silver:'Серебряные',copper:'Медные',platinum:'Платиновые',electrum:'Электрумовые'};
    const rates={gold:100n,silver:10n,copper:1n,platinum:1000n,electrum:50n};
    function previewConversion(){
        const form=root.querySelector('[data-calculator="conversion"]');
        if(!form)return;
        const output=form.querySelector('[data-conversion-preview]');
        const value=form.elements.amount.value;
        if(!/^\d+$/.test(value)||value.length>10){output.textContent='Введи количество монет.';return;}
        const source=form.elements.from_coin.value,target=form.elements.to_coin.value;
        const amount=BigInt(value),received=amount*rates[source]/rates[target];
        const spent=received*rates[target]/rates[source];
        output.textContent=`${coinNames[target]}: ${received}`+(amount-spent>0?` · Остаток исходных: ${amount-spent}`:'');
    }
    root.querySelectorAll('[data-coin-picker]').forEach(picker=>{
        const hidden=picker.querySelector('input'),details=picker.querySelector('details');
        picker.querySelectorAll('[data-coin-choice]').forEach(button=>button.addEventListener('click',()=>{
            hidden.value=button.dataset.coinChoice;
            picker.querySelector('[data-selected-coin]').src=button.querySelector('img').src;
            picker.querySelector('[data-selected-coin-label]').textContent=button.getAttribute('aria-label');
            details.querySelector('summary').setAttribute('aria-label',button.getAttribute('aria-label'));
            picker.querySelectorAll('[data-coin-choice]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
            details.open=false;details.querySelector('summary').focus();
            hidden.dispatchEvent(new Event('change',{bubbles:true}));previewConversion();
        }));
    });
    root.querySelector('[data-calculator="conversion"]')?.addEventListener('input',previewConversion);
    previewConversion();
    async function send(form,action,potion){
        if(form.dataset.busy)return;
        const status=form.querySelector('[role="status"]');
        const data=new FormData(form);data.set('action',action);
        if(potion)data.set('potion',potion);
        form.dataset.busy='true';
        const buttons=[...form.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
        status.textContent='Сохраняю…';
        try{
            const response=await fetch(root.dataset.resourceUrl,{method:'POST',body:data,headers:{'Accept':'application/json'}});
            if(!response.headers.get('content-type')?.includes('application/json'))throw Error('Не удалось сохранить. Проверь вход в аккаунт и обнови страницу.');
            const result=await response.json();
            if(!response.ok)throw Error(result.error||'Не удалось сохранить.');
            paint(result);status.textContent=result.message;
            if(action==='equipment'){
                // Reload only after saving: the server renders tables and spell links safely.
                location.replace(`${location.pathname}#equipment`);
            }else {form.elements.amount.value=action==='convert'?'1':'';previewConversion();}
        }catch(error){status.textContent=error.message;}
        finally{delete form.dataset.busy;buttons.forEach(b=>b.disabled=false);}
    }
    root.querySelectorAll('[data-calculator]').forEach(form=>{
        form.addEventListener('submit',e=>{e.preventDefault();send(form,e.submitter?.value||(form.dataset.calculator==='health'?'heal':form.dataset.calculator==='conversion'?'convert':'take'));});
        form.querySelectorAll('[data-key]').forEach(button=>button.addEventListener('click',()=>{
            const input=form.elements.amount,key=button.dataset.key;
            input.value=key==='back'?input.value.slice(0,-1):input.value+key;
            input.dispatchEvent(new Event('input',{bubbles:true}));
        }));
        form.querySelectorAll('[data-potion]').forEach(button=>button.addEventListener('click',()=>send(form,'potion',button.dataset.potion)));
    });
    root.querySelector('[data-equipment-form]').addEventListener('submit',e=>{
        if(e.defaultPrevented)return;
        e.preventDefault();queueMicrotask(()=>{
            if(e.target.querySelector('[aria-invalid="true"]'))return;
            send(e.target,'equipment');
        });
    });
})();
