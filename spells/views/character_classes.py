from rest_framework import generics
from rest_framework.permissions import AllowAny

from spells.models import CharacterClass
from spells.serializers import CharacterClassSerializer


class CharacterClassListView(generics.ListAPIView):
    """Справочник классов персонажей."""

    queryset = CharacterClass.objects.order_by("name")
    serializer_class = CharacterClassSerializer
    permission_classes = [AllowAny]