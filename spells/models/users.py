from django.db import models
from django.utils.timezone import now


class Player(models.Model):
    """Игрок (пользователь системы)"""

    id = models.AutoField(primary_key=True, verbose_name="id")
    user = models.OneToOneField(
        "auth.User", on_delete=models.CASCADE, related_name="player_profile", verbose_name="Пользователь"
    )
    nickname = models.CharField(max_length=50, blank=True, verbose_name="Ник")
    bio = models.TextField(blank=True, help_text="Краткое описание персонажа", verbose_name="Краткое описание персонажа")
    experience_points = models.IntegerField(
        default=0, help_text="Опыт игрока (не персонажей) в годах", verbose_name="Опыт игрока (не персонажа)"
    )
    favorite_class = models.ForeignKey(
        "spells.CharacterClass",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="favored_by_players",
        verbose_name="Любимый класс"
    )
    telegram_id = models.CharField(max_length=100, blank=True, verbose_name="Телеграмм id")
    avatar = models.ImageField(upload_to="player_avatars/", null=True, verbose_name="Аватар")
    created_at = models.DateTimeField(default=now, verbose_name="Зарегистрировался")
    last_login = models.DateTimeField(default=now, verbose_name="Последний вход")

    def __str__(self):
        return f"{self.nickname or self.user.username}"

    @property
    def total_characters(self):
        return self.characters.count()

    @property
    def active_characters(self):
        return self.characters.filter(is_active=True)

    class Meta:
        verbose_name = "Игрок"
        verbose_name_plural = "Игроки"
