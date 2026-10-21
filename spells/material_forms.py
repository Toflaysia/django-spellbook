import json
from django import forms
from spells.materials import normalize_materials


class MaterialsWidget(forms.Widget):
    template_name='spells/widgets/materials.html'

    def id_for_label(self,id_):
        return id_+'_0_name' if id_ else ''

    def value_from_datadict(self,data,files,name):
        if name+'__present' in data:
            names=data.getlist(name+'_name') if hasattr(data,'getlist') else data.get(name+'_name',[])
            costs=data.getlist(name+'_cost') if hasattr(data,'getlist') else data.get(name+'_cost',[])
            if isinstance(names,str):names=[names]
            if isinstance(costs,str):costs=[costs]
            return [{'name':n,'cost':costs[i] if i<len(costs) else ''} for i,n in enumerate(names)]
        return data.get(name,[])

    def value_omitted_from_data(self,data,files,name):
        return name not in data and name+'__present' not in data

    def get_context(self,name,value,attrs):
        context=super().get_context(name,value,attrs)
        if isinstance(value,str):
            try:value=json.loads(value)
            except ValueError:value=[{'name':value}]
        if not isinstance(value,list):value=[]
        context['widget']['rows']=value or [{'name':'','cost':''}]
        return context


class MaterialsField(forms.Field):
    widget=MaterialsWidget

    def clean(self,value):
        try:return normalize_materials(value)
        except ValueError as error:raise forms.ValidationError(str(error))
