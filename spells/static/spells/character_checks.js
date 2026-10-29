(() => {
    const form=document.getElementById('character-form');
    const source=document.getElementById('character-check-data');
    if(!form||!source)return;
    const data=JSON.parse(source.textContent);
    const nodes=[...form.querySelectorAll('[data-check-kind]')];
    const signed=n=>n>=0?`+${n}`:String(n);
    const value=name=>form.elements.namedItem(name)?.value??'';
    const number=name=>{const v=value(name);return v===''?0:/^-?\d+$/.test(v)?Number(v):NaN;};
    const checked=name=>Boolean(form.elements.namedItem(name)?.checked);
    function refresh(){
        const level=number('primary_class_level')+data.extra_levels;
        const override=value('checks_proficiency_override');
        const pb=override===''?2+Math.floor((Math.max(1,Math.min(20,level))-1)/4):number('checks_proficiency_override');
        const mods=Object.fromEntries(Object.keys(data.abilities).map(k=>[k,value(k)===''?NaN:Math.floor((number(k)-10)/2)]));
        const skills={};
        const totals={none:0,half:Math.floor(pb/2),proficient:pb,expertise:2*pb};
        function skillTotal(group,key,ability){
            const prefix=`checks_${group}_${key}`;
            const stored=group==='skills'?(data.skill_settings[key]||{}):{};
            const trained=totals[value(prefix+'_training')||stored.training||'none'];
            const extra=form.elements.namedItem(prefix+'_bonus')?number(prefix+'_bonus'):(stored.bonus||0);
            return {total:mods[ability]+trained+extra,formula:`${signed(mods[ability])} (${data.abilities[ability]}) ${signed(trained)} (мастерство) ${signed(extra)} (бонус)`};
        }
        for(const [key,,ability] of data.skills)skills[key]=skillTotal('skills',key,ability);
        for(const node of nodes){
            const kind=node.dataset.checkKind,key=node.dataset.checkKey;
            let total,formula;
            if(kind==='skills')({total,formula}=skills[key]);
            if(kind==='saves')({total,formula}=skillTotal(kind,key,key));
            if(kind==='general'){
                const extra=number('checks_initiative_bonus'),half=checked('checks_initiative_half')?Math.floor(pb/2):0;
                total=mods.dexterity+extra+half;
                formula=`${signed(mods.dexterity)} (Ловкость) ${signed(extra)} (бонус) ${signed(half)} (половина мастерства)`;
            }
            if(kind==='passives'){
                const prefix=`checks_passives_${key}`,extra=number(prefix+'_bonus');
                const circumstance=5*(Number(checked(prefix+'_advantage'))-Number(checked(prefix+'_disadvantage')));
                total=10+skills[key].total+extra+circumstance;
                formula=`10 ${signed(skills[key].total)} (навык) ${signed(extra)} (бонус) ${signed(circumstance)} (преимущество/помеха)`;
            }
            if(kind==='speeds'){
                const prefix=`checks_speeds_${key}`,base=number(key==='walk'?'speed':prefix+'_base'),extra=number(prefix+'_bonus');
                const factor=value(prefix+'_factor')||'normal',amount=Math.max(0,base+extra);
                total={normal:amount,half:Math.floor(amount/2),double:amount*2,stopped:0}[factor];
                formula=`(${base} ${signed(extra)}) · ${ {normal:'Обычная',half:'Половина',double:'Удвоенная',stopped:'Обездвижен'}[factor] }`;
            }
            const valid=Number.isFinite(total)&&Number.isFinite(pb);
            node.querySelector('output').textContent=valid?(kind==='general'?`Мастерство ${signed(pb)} · Инициатива ${signed(total)}`:kind==='speeds'?`Итого: ${total} фут.`:kind==='passives'?`Итого: ${total}`:`Итого: ${signed(total)}`):'Заполни характеристику и уровень';
            node.querySelector('.check-formula').textContent=valid?formula:'';
        }
    }
    form.addEventListener('input',refresh);form.addEventListener('change',refresh);refresh();
})();
