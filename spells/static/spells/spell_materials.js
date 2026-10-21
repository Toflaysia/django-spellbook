(() => {
    document.querySelectorAll('[data-materials-widget]').forEach(widget => {
        const rows=widget.querySelector('[data-material-rows]');
        const template=rows.firstElementChild.cloneNode(true);
        let nextId=rows.children.length;
        widget.querySelector('[data-add-material]').addEventListener('click',()=>{
            if(rows.children.length>=100)return;
            const row=template.cloneNode(true);
            row.querySelectorAll('input').forEach(input=>{
                input.value='';
                if(input.id)input.id=input.id.replace(/_\d+_name$/,`_${nextId}_name`);
            });
            nextId++;
            rows.append(row);
            row.querySelector('input').focus();
        });
        widget.addEventListener('click',event=>{
            const button=event.target.closest('[data-remove-material]');
            if(!button)return;
            const row=button.closest('[data-material-row]');
            if(rows.children.length===1)row.querySelectorAll('input').forEach(input=>input.value='');
            else row.remove();
            widget.dispatchEvent(new Event('change',{bubbles:true}));
        });
    });
})();
