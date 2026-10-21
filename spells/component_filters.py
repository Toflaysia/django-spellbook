from django import forms

COMPONENT_CHOICES=[('verbal','Вербальный'),('somatic','Соматический'),('material','Материальный')]


class ComponentsSelect(forms.CheckboxSelectMultiple):
    template_name='spells/widgets/components_select.html'

    def get_context(self,name,value,attrs):
        context=super().get_context(name,value,attrs)
        values=context['widget']['value']
        context['widget']['selected_labels']=', '.join(label for key,label in COMPONENT_CHOICES if key in values)
        return context
