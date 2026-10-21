from django.db import migrations,models
import re
import json
from urllib.parse import unquote


def copy_materials(apps,schema_editor):
    Spell=apps.get_model('spells','Spell')
    for spell in Spell.objects.prefetch_related('material_components').iterator(chunk_size=200):
        items=[{'name':item.name,'cost':str(item.cost) if item.cost is not None else None} for item in spell.material_components.all()]
        # Earlier Foundry imports appended material text instead of saving a relation.
        description=spell.description or ''
        if description.startswith('SPELLBOOK_BLOCKS_V1:'):
            try:
                blocks=json.loads(description[len('SPELLBOOK_BLOCKS_V1:'):])
                description='\n\n'.join(block.get('text','') for block in blocks if isinstance(block,dict))
            except (ValueError,TypeError):description=''
        match=re.search(r'(?:^|\n+)Материальные компоненты: (.*)',description,re.S)
        if not items and match:
            tail=match[1].strip()
            cost=None
            match=re.search(r'\n+Стоимость компонентов: ([0-9]+(?:[.,][0-9]{1,2})?) зм\.$',tail)
            if match:
                cost=match[1].replace(',','.');tail=tail[:match.start()]
            tail=re.sub(r'\n+Компоненты расходуются\.$','',tail).strip()
            tail=re.sub(r'\[\[[a-z]+:[^|\n]+\|([^\]\n]*)\]\]',lambda match:unquote(match[1]),tail)
            if tail:items=[{'name':tail,'cost':cost}]
        Spell.objects.filter(pk=spell.pk).update(material_components_data=items)


def restore_materials(apps,schema_editor):
    Spell=apps.get_model('spells','Spell');Component=apps.get_model('spells','MaterialComponent')
    for spell in Spell.objects.iterator():
        for item in spell.material_components_data:
            component=Component.objects.create(name=item['name'],cost=item.get('cost'))
            spell.material_components.add(component)


class Migration(migrations.Migration):
    dependencies=[('spells','0019_email_accounts_and_reminders')]
    operations=[
        migrations.AddField(model_name='spell',name='material_components_data',field=models.JSONField(blank=True,default=list,verbose_name='Материальные компоненты')),
        migrations.RunPython(copy_materials,restore_materials),
        migrations.RemoveField(model_name='spell',name='material_components'),
        migrations.RenameField(model_name='spell',old_name='material_components_data',new_name='material_components'),
    ]
