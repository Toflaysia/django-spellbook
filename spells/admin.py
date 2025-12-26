from django.contrib import admin

from spells.models import (CharacterClass, DamageType, Effect, MagicSchool,
                           MaterialComponent, Person, Player, Spell, Spellbook,
                           SpellTime, Subclass)

# Register your models here.
admin.site.register(CharacterClass)
admin.site.register(DamageType)
admin.site.register(Effect)
admin.site.register(MagicSchool)
admin.site.register(MaterialComponent)
admin.site.register(Person)
admin.site.register(Player)
admin.site.register(Spell)
admin.site.register(Spellbook)
admin.site.register(SpellTime)
admin.site.register(Subclass)





