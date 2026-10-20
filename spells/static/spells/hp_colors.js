(() => {
    document.querySelectorAll('form').forEach(form => {
        const current=form.querySelector('input[name="current_hit_points"]');
        const maximum=form.querySelector('input[name="max_hit_points"]');
        if(!current||!maximum)return;
        const paint=()=>{
            current.classList.add('hp-current');
            current.classList.toggle('hp-low',current.value!==''&&maximum.value!==''&&Number(current.value)*2<=Number(maximum.value));
        };
        current.addEventListener('input',paint);maximum.addEventListener('input',paint);paint();
    });
})();
