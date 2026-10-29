from django import forms


class TrainingCircles(forms.RadioSelect):
    template_name='spells/widgets/training_circles.html'

    def create_option(self,*args,**kwargs):
        option=super().create_option(*args,**kwargs)
        option['symbol']={'none':'○','half':'◐','proficient':'●','expertise':'◎'}.get(str(option['value']),'○')
        return option
