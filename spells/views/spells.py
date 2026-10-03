from rest_framework import generics, serializers
from rest_framework.filters import SearchFilter
from rest_framework.permissions import AllowAny

from spells.models import Spell
from spells.serializers import SpellSerializer


class SpellFilterSerializer(serializers.Serializer):
    level = serializers.IntegerField(
        required=False,
        min_value=0,
        max_value=9,
    )
    school = serializers.IntegerField(
        required=False,
        min_value=1,
    )


class SpellCatalogMixin:
    serializer_class = SpellSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return (
            Spell.objects.filter(is_official=True)
            .select_related("school", "time")
            .prefetch_related(
                "material_components",
                "effects",
                "aviable_classes",
                "aviable_subclasses",
            )
        )


class SpellListView(SpellCatalogMixin, generics.ListAPIView):
    """Каталог официальных заклинаний с поиском и фильтрами."""

    filter_backends = [SearchFilter]
    search_fields = ["name", "description"]

    def get_queryset(self):
        filters = SpellFilterSerializer(
            data=self.request.query_params,
        )
        filters.is_valid(raise_exception=True)

        queryset = super().get_queryset()

        if "level" in filters.validated_data:
            queryset = queryset.filter(
                level=filters.validated_data["level"],
            )

        if "school" in filters.validated_data:
            queryset = queryset.filter(
                school_id=filters.validated_data["school"],
            )

        return queryset


class SpellDetailView(SpellCatalogMixin, generics.RetrieveAPIView):
    """Просмотр официального заклинания."""