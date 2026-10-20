from django.conf import settings
from django.db import models
from django.utils import timezone

class HomePlan(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='spellbook_plans')
    title = models.CharField(max_length=200, verbose_name='План или напоминание')
    text = models.TextField(blank=True, verbose_name='Подробности')
    reminder_date = models.DateField(blank=True, null=True, verbose_name='Напомнить к дате')
    is_done = models.BooleanField(default=False, verbose_name='Выполнено')
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def reminder_status(self):
        if self.is_done or not self.reminder_date:
            return ''
        today = timezone.localdate()
        if self.reminder_date < today:
            return 'Просрочено'
        if self.reminder_date == today:
            return 'Сегодня'
        return ''

    class Meta:
        verbose_name='План или напоминание'
        verbose_name_plural='Планы и напоминания'

    def __str__(self):
        return self.title
