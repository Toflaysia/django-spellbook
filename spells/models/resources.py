from django.db import models
from django.core.validators import MinValueValidator,MaxValueValidator
from django.core.exceptions import ValidationError


class CharacterResource(models.Model):
    person=models.ForeignKey('spells.Person',on_delete=models.CASCADE,related_name='rest_resources')
    name=models.CharField(max_length=80,verbose_name='Название')
    maximum=models.PositiveIntegerField(default=1,validators=[MinValueValidator(1),MaxValueValidator(9999)],verbose_name='Максимум')
    current=models.PositiveIntegerField(default=1,verbose_name='Осталось')
    refresh_on=models.CharField(max_length=6,choices=[('short','Короткий и длинный отдых'),('long','Длинный отдых'),('manual','Только вручную')],default='long',verbose_name='Восстановление')

    def clean(self):
        super().clean()
        if self.current>self.maximum:raise ValidationError({'current':'Текущее значение не может превышать максимум.'})

    class Meta:
        ordering=['name','pk']
        verbose_name='Ресурс персонажа'
        constraints=[models.CheckConstraint(condition=models.Q(current__lte=models.F('maximum')),name='resource_current_lte_maximum'),models.CheckConstraint(condition=models.Q(maximum__gte=1,maximum__lte=9999),name='resource_maximum_range')]
