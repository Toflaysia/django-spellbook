(() => {
    for (const [className, levelName, subName] of [['character_class','primary_class_level','subclass'], ['second_class','second_class_level','second_subclass']]) {
        const cls=document.getElementById('id_'+className),level=document.getElementById('id_'+levelName),sub=document.getElementById('id_'+subName);
        if(!cls||!level||!sub)continue;
        const choices=JSON.parse(sub.dataset.subclassOptions||'[]');
        // В списке остаются подклассы выбранного класса, доступные на введённом уровне.
        function paint(){
            const chosen=sub.value;
            sub.replaceChildren(new Option('Без подкласса',''));
            choices.filter(row=>String(row.class_id)===cls.value && row.level<=Number(level.value)).forEach(row=>sub.add(new Option(row.name,row.id)));
            if([...sub.options].some(option=>option.value===chosen))sub.value=chosen;
        }
        cls.addEventListener('change',paint);level.addEventListener('input',paint);paint();
    }
})();
