"""Validate and import independent spell records with an administrator report."""
import logging
from django.contrib.auth.models import AnonymousUser
from django.db import transaction, IntegrityError
from spells.models import Spell, Player
from spells.forms import CustomSpellForm
from spells.spell_import import build_spell_initial
from spells.import_links import ImportLinker, key

logger=logging.getLogger(__name__)


def import_spell_records(records,user,*,sources=None):
    results=[];created=[]
    with transaction.atomic():
        existing={key(name) for name in Spell.objects.values_list('name',flat=True)}
        player,_=Player.objects.get_or_create(user=user)
        for index,data in enumerate(records,1):
            name=data.get('name','') if isinstance(data,dict) else ''
            row={'index':index,'name':name if isinstance(name,str) else 'Без названия','status':'error','messages':[],'warnings':[]}
            row['source']=sources[index-1] if sources else ''
            results.append(row)
            try:
                initial=build_spell_initial(data,user=AnonymousUser(),auto_links=False)
                normalized=key(initial['name'])
                if normalized in existing:
                    row.update(status='duplicate',messages=['Запись с таким названием уже существует. Она не изменена.'])
                    continue
                form=CustomSpellForm(initial,user=user)
                form.fields.pop('is_public',None)
                if not form.is_valid():
                    row['messages']=[str(form.fields[field].label if field in form.fields else 'Запись')+': '+str(message) for field,errors in form.errors.items() for message in errors]
                    continue
                with transaction.atomic():
                    spell=form.save(commit=False)
                    spell.created_by=player;spell.is_official=True;spell.is_public=False
                    spell.save();form.save_m2m()
                existing.add(normalized)
                created.append((spell,row))
                row.update(status='created',pk=spell.pk)
            except (ValueError,TypeError,KeyError,OverflowError,RecursionError) as error:
                row['messages']=[str(error)]
            except IntegrityError:
                row['messages']=['Не удалось сохранить запись: название уже занято или данные нарушают ограничения базы.']
                logger.exception('Spell import row %s failed integrity validation',index)
        # Build the index after creation so references to later rows also work.
        linker=ImportLinker(AnonymousUser())
        for spell,row in created:
            linker.warnings.clear()
            spell.description=linker.description(spell.description)
            spell.higher_level=linker.description(spell.higher_level)
            spell.save(update_fields=['description','higher_level'])
            row['warnings']=sorted(linker.warnings)
    return {
        'rows':results,'created':sum(r['status']=='created' for r in results),
        'duplicates':sum(r['status']=='duplicate' for r in results),
        'errors':sum(r['status']=='error' for r in results),
    }
