from django.db import migrations, models
import spells.character_checks


def preserve_bonuses(apps, schema_editor):
    Person=apps.get_model('spells','Person')
    for person in Person.objects.using(schema_editor.connection.alias).all().iterator():
        level=person.primary_class_level+person.second_class_level+person.warlock_level
        expected=2+(max(1,min(20,level))-1)//4
        # Preserve an existing nonstandard bonus as an explicit override.
        if person.proficiency_bonus!=expected:
            person.check_settings={'proficiency_override':person.proficiency_bonus}
            person.save(update_fields=['check_settings'],using=schema_editor.connection.alias)


class Migration(migrations.Migration):
    dependencies=[('spells','0020_spell_local_materials')]
    operations=[
        migrations.AddField(model_name='person',name='check_settings',field=models.JSONField(blank=True,default=dict,validators=[spells.character_checks.validate_check_settings],verbose_name='Навыки и расчёты')),
        migrations.RunPython(preserve_bonuses,migrations.RunPython.noop),
    ]
