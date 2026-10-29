import json
from io import StringIO
from django.test import TestCase
from django.contrib.auth.models import AnonymousUser, User
from django.core.management import call_command, CommandError
from spells.models import Spell, Effect, Trait, Player, SpellTime, MagicSchool
from spells.import_links import ImportLinker
from spells.bulk_import import import_spell_records
from spells.description import DESCRIPTION_PREFIX
from spells.templatetags.description_tags import render_description


class FoundryReferenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('author')
        cls.player = Player.objects.create(user=cls.user)
        cls.target = Spell.objects.create(name='Обнаружение мыслей [Detect Thoughts]', description='Текст', duration='Миг', is_official=True)
        cls.condition = Effect.objects.create(name='Испуганный', category='COND')
        Trait.objects.create(name='Испуганный')
        cls.private = Spell.objects.create(name='Тайная мысль',description='Секрет',duration='Миг',is_official=False,created_by=cls.player)

    def linker(self):
        return ImportLinker(AnonymousUser())

    def test_user_example_bilingual_names_and_fallback(self):
        source='Лента как @Compendium[laaru-dnd5-hw.conditions.sDPntYBdmN7jMZc6]{маленький} предмет. @Compendium[laaru-dnd5-hw.spells.MSM1XtWei12DFoLN]{Обнаружение мыслей}. @Compendium[laaru-dnd5-hw.spells.ujIJlxgzYuog6Nkk]{Манипуляция памятью}.'
        result=self.linker().description(source)
        self.assertNotIn('@Compendium',result)
        self.assertIn('как маленький предмет.',result)
        self.assertIn(f'[[spell:{self.target.pk}|',result)
        self.assertTrue(result.endswith('Манипуляция памятью.'))
        self.assertIn('Обнаружение мыслей',str(render_description(result)))

    def test_uuid_category_disambiguation_and_external_id_never_used(self):
        result=self.linker().description('@UUID[Compendium.pack.conditions.Item.999999]{Испуганный}')
        self.assertIn(f'[[condition:{self.condition.pk}|',result)
        self.assertNotIn('999999',result)
        self.assertEqual(self.linker().description('@UUID[Compendium.pack.spells.Item.999999]{Испуганный}'),'Испуганный')

    def test_dice_ids_and_existing_tokens_are_not_reinterpreted(self):
        linker=self.linker()
        token='[[spell:12|%40Compendium%5Bx%5D%7By%7D]]'
        value=linker.description(token+' @Compendium[pack.spells.1d20]{Несуществующая запись} [[/r 2к6+3]]')
        self.assertTrue(value.startswith(token+' Несуществующая запись '))
        self.assertEqual(value.count('[[dice:'),1)
        self.assertEqual(linker.description(value),value)

    def test_missing_label_and_ambiguous_or_private_target(self):
        linker=self.linker()
        self.assertEqual(linker.description('@UUID[Item.external]'),'')
        self.assertEqual(linker.description('@Compendium[pack.spells.id]{Тайная мысль}'),'Тайная мысль')
        self.assertEqual(linker.description('@Compendium[pack.unknown.id]{Испуганный}'),'Испуганный')
        self.assertTrue(linker.warnings)

    def test_structured_blocks_repair_preserves_other_links_and_text(self):
        text='@Compendium[pack.spells.id]{Обнаружение мыслей} 1d6 [[condition:7|Своя%20подпись]]'
        blocks=[{'type':'text','text':text},{'type':'heading','text':text},{'type':'quote','text':text},{'type':'list','items':[text]},{'type':'table','rows':[[text]]}]
        value=self.linker().description(DESCRIPTION_PREFIX+json.dumps(blocks),references_only=True)
        self.assertNotIn('@Compendium',value)
        self.assertEqual(value.count(f'[[spell:{self.target.pk}|'),5)
        self.assertEqual(value.count('[[condition:7|Своя%20подпись]]'),5)
        self.assertNotIn('[[dice:',value)
        self.assertEqual(self.linker().description(value,references_only=True),value)

    def test_bulk_foundry_forward_reference_and_report(self):
        SpellTime.objects.create(time='Действие');MagicSchool.objects.create(name='Воплощение')
        def record(name,text):
            return {'name':name,'type':'spell','system':{'school':'evo','level':1,'activation':{'type':'action'},'duration':{'units':'inst'},'description':{'value':'<p>'+text+'</p>'}}}
        report=import_spell_records([record('Первое','@Compendium[pack.spells.id]{Второе} @Compendium[pack.conditions.id]{Нет состояния}'),record('Второе','Текст')],self.user)
        self.assertEqual(report['created'],2,report)
        first=Spell.objects.get(name='Первое');second=Spell.objects.get(name='Второе')
        self.assertIn(f'[[spell:{second.pk}|',first.description)
        self.assertNotIn('@Compendium',first.description)
        self.assertTrue(report['rows'][0]['warnings'])

    def test_repair_command_respects_visibility_and_is_repeatable(self):
        text='@Compendium[pack.spells.id]{Тайная мысль}'
        public=Spell.objects.create(name='Публичное',description=text,higher_level='@Compendium[pack.spells.id]{Обнаружение мыслей}',duration='Миг',is_official=True,created_by=self.player)
        private=Spell.objects.create(name='Личное',description=text,duration='Миг',is_official=False,created_by=self.player)
        unrelated=Spell.objects.create(name='Без разметки',description='1d6 [[spell:9|Своё]]',duration='Миг')
        call_command('repair_foundry_links',stdout=StringIO())
        public.refresh_from_db();private.refresh_from_db();unrelated.refresh_from_db()
        self.assertEqual(public.description,'Тайная мысль')
        self.assertIn(f'[[spell:{self.target.pk}|',public.higher_level)
        self.assertIn(f'[[spell:{self.private.pk}|',private.description)
        self.assertEqual(unrelated.description,'1d6 [[spell:9|Своё]]')
        output=StringIO();call_command('repair_foundry_links',stdout=output)
        self.assertIn('Исправлено заклинаний: 0.',output.getvalue())

    def test_bad_structured_data_rolls_back_prior_repairs(self):
        first=Spell.objects.create(name='До ошибки',description='@Compendium[p.spells.id]{Обнаружение мыслей}',duration='Миг')
        Spell.objects.create(name='Ошибка',description=DESCRIPTION_PREFIX+'[{"type":"bad","text":"@Compendium[p.id]{X}"}]',duration='Миг')
        with self.assertRaises(CommandError):call_command('repair_foundry_links',stdout=StringIO())
        first.refresh_from_db();self.assertTrue(first.description.startswith('@Compendium'))
