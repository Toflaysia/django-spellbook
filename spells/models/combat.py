from django.db import models


class CharacterCondition(models.Model):
    person = models.ForeignKey('spells.Person', on_delete=models.CASCADE, related_name='active_conditions')
    condition = models.ForeignKey('spells.Effect', on_delete=models.CASCADE, limit_choices_to={'category': 'COND'})
    note = models.CharField(max_length=200, blank=True, verbose_name='Источник или срок действия')
    incapacitates = models.BooleanField(default=False, verbose_name='Лишает дееспособности')

    class Meta:
        ordering = ['condition__name', 'pk']
        constraints = [models.UniqueConstraint(fields=['person', 'condition'], name='unique_person_condition')]


class ConcentrationCheck(models.Model):
    person = models.ForeignKey('spells.Person', on_delete=models.CASCADE, related_name='concentration_checks')
    damage = models.PositiveIntegerField(default=0)
    dc = models.PositiveIntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']
