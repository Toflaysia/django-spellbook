from django import forms
from spells.models import Player


class ProfileForm(forms.ModelForm):
    nickname=forms.CharField(label='Имя в профиле',max_length=50,required=False,help_text='Если оставить пустым, будет показано имя пользователя.')
    bio=forms.CharField(label='О себе',max_length=1000,required=False,widget=forms.Textarea(attrs={'rows':5}))

    class Meta:
        model=Player
        fields=['nickname','avatar','table_role','bio','show_activity']
        labels={'avatar':'Аватар','table_role':'Роль за столом','show_activity':'Показывать, когда я в сети и когда был(а) активен(на)'}
        help_texts={'avatar':'PNG, JPEG или WebP, до 2 МБ и 2048 × 2048 пикселей.','show_activity':'Статус «В сети» означает активность на сайте за последние 5 минут.'}

    def clean_avatar(self):
        avatar=self.cleaned_data.get('avatar')
        if avatar and 'avatar' in self.changed_data:
            if avatar.size>2*1024*1024:raise forms.ValidationError('Изображение должно быть не больше 2 МБ.')
            image=getattr(avatar,'image',None)
            if image is None or image.format not in {'PNG','JPEG','WEBP'}:raise forms.ValidationError('Выбери PNG, JPEG или WebP.')
            if max(image.size)>2048:raise forms.ValidationError('Размер изображения не должен превышать 2048 × 2048 пикселей.')
        return avatar
