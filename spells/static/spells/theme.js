(() => {
    const key='spellbook.theme';
    const valid=value=>value==='light'||value==='dark';
    const root=document.documentElement;
    let initial='dark';
    try{const saved=localStorage.getItem(key);if(valid(saved))initial=saved;}catch{}
    function apply(theme){
        root.dataset.theme=theme;
        document.querySelectorAll('[data-theme-toggle]').forEach(button=>{
            button.setAttribute('aria-pressed',String(theme==='light'));
            button.title=theme==='light'?'Включить тёмную тему':'Включить светлую тему';
        });
    }
    apply(initial);
    document.addEventListener('DOMContentLoaded',()=>{
        apply(root.dataset.theme);
        document.querySelectorAll('[data-theme-toggle]').forEach(button=>button.addEventListener('click',()=>{
            const theme=root.dataset.theme==='light'?'dark':'light';
            apply(theme);
            try{localStorage.setItem(key,theme);}catch{}
        }));
    });
    window.addEventListener('storage',event=>{
        if(event.key===key)apply(valid(event.newValue)?event.newValue:'dark');
        else if(event.key===null)apply('dark');
    });
})();
