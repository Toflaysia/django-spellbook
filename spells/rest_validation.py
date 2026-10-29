from django.core.exceptions import ValidationError

DICE=(2,4,6,8,10,12,20,100)


def validate_spent_hit_dice(value):
    if not isinstance(value,dict) or any(key not in {str(n) for n in DICE} or type(count) is not int or not 0<=count<=60 for key,count in value.items()):
        raise ValidationError('Неверные значения потраченных костей хитов.')
