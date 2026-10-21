from django.contrib import admin
from spells.description import DescriptionModelForm
from spells.models import ClassFeature, ClassSection

from spells.models import (CharacterClass, DamageType, Effect, MagicSchool,
                           MaterialComponent, Person, Player, Spell, Spellbook,
                           SpellTime, Subclass)

class DescriptionAdmin(admin.ModelAdmin):
    form = DescriptionModelForm


admin.site.register(CharacterClass, DescriptionAdmin)
admin.site.register(DamageType, DescriptionAdmin)
admin.site.register(Effect, DescriptionAdmin)
admin.site.register(MagicSchool, DescriptionAdmin)
admin.site.register(Person, DescriptionAdmin)
admin.site.register(Player)
admin.site.register(Spell, DescriptionAdmin)
admin.site.register(Spellbook, DescriptionAdmin)
admin.site.register(SpellTime, DescriptionAdmin)
admin.site.register(Subclass, DescriptionAdmin)






admin.site.register(ClassFeature, DescriptionAdmin)
admin.site.register(ClassSection, DescriptionAdmin)

from spells.models import Trait
admin.site.register(Trait, DescriptionAdmin)

from spells.models import AccountEmail, HomePlan

@admin.register(AccountEmail)
class AccountEmailAdmin(admin.ModelAdmin):
    list_display=('user','email','verified_at')
    readonly_fields=('user','email','verified_at','confirmation_sent_at','password_reset_sent_at')

    def has_add_permission(self,request):
        return False

admin.site.register(HomePlan)
