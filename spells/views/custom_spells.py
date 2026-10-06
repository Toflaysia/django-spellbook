from rest_framework import generics
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated

from spells.models import Player, Spell
from spells.serializers import CustomSpellSerializer


class CustomSpellQuerysetMixin:
    serializer_class = CustomSpellSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Spell.objects.filter(
                created_by__user=self.request.user,
                is_official=False,
            )
            .select_related("school", "time")
            .prefetch_related(
                "material_components",
                "effects",
                "aviable_classes",
                "aviable_subclasses",
            )
        )


class CustomSpellListCreateView(
    CustomSpellQuerysetMixin,
    generics.ListCreateAPIView,
):
    """Список своих заклинаний и создание заклинания."""

    filter_backends = [SearchFilter]
    search_fields = ["name", "description"]

    def perform_create(self, serializer):
        player, _ = Player.objects.get_or_create(
            user=self.request.user,
        )
        serializer.save(
            created_by=player,
            is_official=False,
        )


class CustomSpellDetailView(
    CustomSpellQuerysetMixin,
    generics.RetrieveUpdateDestroyAPIView,
):
    """Просмотр, изменение и удаление своего заклинания."""