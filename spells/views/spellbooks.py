from rest_framework import generics
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from django.db.models import F
from django.utils.timezone import now
from rest_framework import serializers
from rest_framework.response import Response
from spells.models import Spellbook
from spells.serializers import SpellbookSerializer


class SpellbookQuerysetMixin:
    serializer_class = SpellbookSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Spellbook.objects.filter(
                owner__player__user=self.request.user,
            )
            .select_related("owner", "owner__player")
            .prefetch_related("spells")
        )


class SpellbookListCreateView(
    SpellbookQuerysetMixin,
    generics.ListCreateAPIView,
):
    """Список своих спеллбуков и создание спеллбука."""

    filter_backends = [SearchFilter]
    search_fields = ["name", "owner__name"]


class SpellbookDetailView(
    SpellbookQuerysetMixin,
    generics.RetrieveUpdateDestroyAPIView,
):
    """Просмотр, изменение и удаление своего спеллбука."""
class UseSpellSlotSerializer(serializers.Serializer):
    level = serializers.IntegerField(min_value=1, max_value=9)


class SpellbookUseSlotView(
    SpellbookQuerysetMixin,
    generics.GenericAPIView,
):
    """Расход одной ячейки указанного уровня."""

    def post(self, request, *args, **kwargs):
        data = UseSpellSlotSerializer(data=request.data)
        data.is_valid(raise_exception=True)

        spellbook = self.get_object()
        level = data.validated_data["level"]
        field_name = f"current_spell_slots_{level}"

        updated = Spellbook.objects.filter(
            pk=spellbook.pk,
            **{f"{field_name}__gt": 0},
        ).update(
            **{field_name: F(field_name) - 1},
            last_used=now(),
            updated_at=now(),
        )

        if not updated:
            raise serializers.ValidationError({
                "level": "Ячейки этого уровня закончились.",
            })

        spellbook.refresh_from_db()
        return Response(self.get_serializer(spellbook).data)
class SpellbookRestView(
    SpellbookQuerysetMixin,
    generics.GenericAPIView,
):
    """Восстановление всех ячеек спеллбука."""

    def post(self, request, *args, **kwargs):
        spellbook = self.get_object()

        restored_slots = {
            f"current_spell_slots_{level}": F(
                f"max_spell_slots_{level}"
            )
            for level in range(1, 10)
        }

        Spellbook.objects.filter(pk=spellbook.pk).update(
            **restored_slots,
            warlock_current_slots=F("warlock_max_slots"),
            updated_at=now(),
        )

        spellbook.refresh_from_db()
        return Response(self.get_serializer(spellbook).data)