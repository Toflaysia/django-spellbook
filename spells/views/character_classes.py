from spells.class_access import visible_classes
from rest_framework import generics
from rest_framework.permissions import AllowAny

from spells.models import CharacterClass
from spells.serializers import CharacterClassSerializer


class CharacterClassListView(generics.ListAPIView):
    """Справочник классов персонажей."""

    def get_queryset(self):
        return visible_classes(self.request.user).order_by("name", "pk")
    serializer_class = CharacterClassSerializer
    permission_classes = [AllowAny]