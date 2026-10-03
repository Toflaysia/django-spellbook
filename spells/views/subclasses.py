from rest_framework import generics, serializers
from rest_framework.permissions import AllowAny

from spells.models import Subclass
from spells.serializers import SubclassSerializer


class SubclassFilterSerializer(serializers.Serializer):
    character_class = serializers.IntegerField(
        required=False,
        min_value=1,
    )


class SubclassListView(generics.ListAPIView):
    """Справочник подклассов с фильтром по классу."""

    serializer_class = SubclassSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        filters = SubclassFilterSerializer(
            data=self.request.query_params,
        )
        filters.is_valid(raise_exception=True)

        queryset = Subclass.objects.order_by("name")
        class_id = filters.validated_data.get("character_class")

        if class_id is not None:
            queryset = queryset.filter(character_class_id=class_id)

        return queryset