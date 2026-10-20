(() => {
    const form=document.querySelector('[data-school-color]');
    if(!form)return;
    const color=form.querySelector('[name="color"]');
    const picker=form.querySelector('[data-school-color-picker]');
    if(!color)return;
    const paint=()=>{
        if(/^#[0-9a-f]{6}$/i.test(color.value)){
            form.style.setProperty('--school-color',color.value);
            if(picker)picker.value=color.value;
        }
    };
    color.addEventListener('input',paint);
    picker?.addEventListener('input',()=>{
        color.value=picker.value;
        color.dispatchEvent(new Event('input',{bubbles:true}));
    });
    paint();
})();
