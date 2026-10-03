from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.filters import SearchFilter

from spells.models import Person, Player
from spells.serializers import CharacterSerializer


class CharacterQuerysetMixin:
    serializer_class = CharacterSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Person.objects.filter(
            player__user=self.request.user
        ).select_related(
            "player",
            "character_class",
            "subclass",
        )


class CharacterListCreateView(
    CharacterQuerysetMixin,
    generics.ListCreateAPIView,
):
    """Список своих персонажей и создание персонажа."""

    filter_backends = [SearchFilter]
    search_fields = ["name"]

    def perform_create(self, serializer):
        player, _ = Player.objects.get_or_create(
            user=self.request.user,
        )
        serializer.save(player=player)

    """Список своих персонажей и создание персонажа."""

    def perform_create(self, serializer):
        player, _ = Player.objects.get_or_create(
            user=self.request.user,
        )
        serializer.save(player=player)

class PublicCharacterDetailView(generics.RetrieveAPIView):
    """Просмотр публичного персонажа."""

    queryset = Person.objects.filter(
        is_public=True,
    ).select_related(
        "player",
        "character_class",
        "subclass",
    )
    serializer_class = CharacterSerializer
    permission_classes = [AllowAny]
    
class CharacterDetailView(
    CharacterQuerysetMixin,
    generics.RetrieveUpdateDestroyAPIView,
):
    """Просмотр, изменение и удаление своего персонажа."""