"""Spell-local material names and optional prices, independent of catalogs."""
from decimal import Decimal, InvalidOperation


def normalize_materials(value):
    if value is None or value == '':
        return []
    if isinstance(value,str):
        value=[{'name':value}]
    if isinstance(value,dict):
        value=[value]
    if not isinstance(value,list) or len(value)>100:
        raise ValueError('Материальные компоненты: нужен список, не больше 100 компонентов.')
    result=[]
    for item in value:
        if isinstance(item,str):item={'name':item}
        if not isinstance(item,dict):
            raise ValueError('Материальные компоненты: укажи название и стоимость, а не ID справочника.')
        name=item.get('name','')
        if not isinstance(name,str):raise ValueError('Название материального компонента должно быть текстом.')
        name=name.strip()
        cost=item.get('cost')
        if not name and cost in (None,''):continue
        if not name:raise ValueError('Укажи название материального компонента рядом со стоимостью.')
        if len(name)>5000:raise ValueError('Название материального компонента длиннее 5000 символов.')
        if cost not in (None,''):
            try:
                if isinstance(cost,bool):raise InvalidOperation()
                number=Decimal(str(cost).replace(',','.'))
                if not number.is_finite() or number<0 or number>=Decimal('10000000000') or number.as_tuple().exponent < -2:raise InvalidOperation()
                cost=format(number,'f')
            except (InvalidOperation,ValueError,TypeError):
                raise ValueError('Стоимость компонента должна быть неотрицательным числом, не более двух знаков после запятой.')
        else:cost=None
        result.append({'name':name,'cost':cost})
    return result
