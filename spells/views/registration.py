from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import generics, serializers
from rest_framework.permissions import AllowAny

from spells.models import Player


User = get_user_model()


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )
    password_confirm = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "password",
            "password_confirm",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({
                "password_confirm": "Пароли не совпадают.",
            })

        user = User(username=attrs["username"])

        try:
            validate_password(attrs["password"], user=user)
        except ValidationError as error:
            raise serializers.ValidationError({
                "password": error.messages,
            }) from error

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop("password_confirm")

        user = User.objects.create_user(**validated_data)
        Player.objects.create(user=user)

        return user


class RegistrationView(generics.CreateAPIView):
    """Регистрация нового игрока."""

    serializer_class = RegistrationSerializer
    permission_classes = [AllowAny]