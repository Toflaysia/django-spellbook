from django.urls import path
from spells.views.character_classes import CharacterClassListView
from spells.views.registration import RegistrationView
from spells.views.subclasses import SubclassListView
from spells.views.spells import SpellDetailView, SpellListView

from spells.views.spellbooks import (
    SpellbookDetailView,
    SpellbookListCreateView,
    SpellbookRestView,
    SpellbookUseSlotView,
)
from spells.views.spellbooks import (
    SpellbookDetailView,
    SpellbookListCreateView,
    SpellbookUseSlotView,
)
from spells.views.spellbooks import (
    SpellbookDetailView,
    SpellbookListCreateView,
)
from spells.views.custom_spells import (
    CustomSpellDetailView,
    CustomSpellListCreateView,
)
from spells.views.characters import (
    CharacterDetailView,
    CharacterListCreateView,
    PublicCharacterDetailView,
)
from spells.views.material_component import (
    MaterialComponentDetailView,
    MaterialConponentListView,
)

app_name = "spells"

urlpatterns = [
    path(
        "material_component/",
        MaterialConponentListView.as_view(),
    ),
    path(
        "material_component/<int:id>/",
        MaterialComponentDetailView.as_view(),
        name="material_component_detail",
    ),
    path(
        "characters/",
        CharacterListCreateView.as_view(),
        name="character_list",
    ),
    path(
        "characters/<int:pk>/",
        CharacterDetailView.as_view(),
        name="character_detail",
    ),
    path(
        "classes/",
        CharacterClassListView.as_view(),
        name="character_class_list",
    ),
    path(
        "register/",
        RegistrationView.as_view(),
        name="register",
    ),    
        path(
        "public/characters/<int:pk>/",
        PublicCharacterDetailView.as_view(),
        name="public_character_detail",
    ),
        path(
        "subclasses/",
        SubclassListView.as_view(),
        name="subclass_list",
    ),
        path(
        "spells/",
        SpellListView.as_view(),
        name="spell_list",
    ),
    path(
        "spells/<int:pk>/",
        SpellDetailView.as_view(),
        name="spell_detail",
    ),
        path(
        "my-spells/",
        CustomSpellListCreateView.as_view(),
        name="custom_spell_list",
    ),
    path(
        "my-spells/<int:pk>/",
        CustomSpellDetailView.as_view(),
        name="custom_spell_detail",
    ),
        path(
        "spellbooks/",
        SpellbookListCreateView.as_view(),
        name="spellbook_list",
    ),
    path(
        "spellbooks/<int:pk>/",
        SpellbookDetailView.as_view(),
        name="spellbook_detail",
    ),
        path(
        "spellbooks/<int:pk>/use-slot/",
        SpellbookUseSlotView.as_view(),
        name="spellbook_use_slot",
    ),
        path(
        "spellbooks/<int:pk>/rest/",
        SpellbookRestView.as_view(),
        name="spellbook_rest",
    ),
]