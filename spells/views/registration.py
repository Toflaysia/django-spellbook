from spells.models import AccountEmail
from spells.email_accounts import normalize_email, email_available, send_confirmation
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import generics, serializers
from rest_framework.permissions import AllowAny

from spells.models import Player


User = get_user_model()


class RegistrationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    email_confirmation_status = serializers.SerializerMethodField()

    def get_email_confirmation_status(self, user):
        return getattr(user,'_email_confirmation_status','')

    def validate_username(self,value):
        if '@' in value:raise serializers.ValidationError('Имя пользователя укажи без @.')
        return value

    def validate_email(self, value):
        value=normalize_email(value)
        if not email_available(value):raise serializers.ValidationError('Этот email уже используется.')
        return value

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
            "email",
            "email_confirmation_status",
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

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        try:
            with transaction.atomic():
                user=User.objects.create_user(**validated_data)
                Player.objects.create(user=user)
                AccountEmail.objects.create(user=user,email=user.email)
        except IntegrityError:
            raise serializers.ValidationError({'email':'Email или имя пользователя уже заняты.'})
        user._email_confirmation_status=send_confirmation(user)
        return user


class RegistrationView(generics.CreateAPIView):
    """Регистрация нового игрока."""

    serializer_class = RegistrationSerializer
    permission_classes = [AllowAny]