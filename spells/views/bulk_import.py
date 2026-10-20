import json
import logging
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from spells.bulk_import import import_spell_records

logger=logging.getLogger(__name__)


class MultipleJSONInput(forms.ClearableFileInput):
    allow_multiple_selected=True


class MultipleJSONField(forms.FileField):
    def clean(self,data,initial=None):
        if not data:
            return super().clean(data,initial)
        files=data if isinstance(data,(list,tuple)) else [data]
        return [super(MultipleJSONField,self).clean(file,initial) for file in files]


class BulkSpellImportForm(forms.Form):
    json_file=MultipleJSONField(label='JSON-файлы заклинаний',allow_empty_file=True,help_text='Можно выбрать несколько файлов через Ctrl или Shift. До 100 файлов, 5 МБ на файл, 20 МБ суммарно и 500 записей.',widget=MultipleJSONInput(attrs={'accept':'.json,application/json'}))

    def clean_json_file(self):
        files=self.cleaned_data['json_file']
        if len(files)>100:raise forms.ValidationError('Выбери не больше 100 файлов.')
        if sum(file.size for file in files)>20*1024*1024:raise forms.ValidationError('Общий размер файлов больше 20 МБ.')
        self.records=[];self.sources=[];self.file_errors=[]
        for uploaded in files:
            try:
                records=self.read_records(uploaded)
            except forms.ValidationError as error:
                self.file_errors.append({'name':uploaded.name,'messages':error.messages})
                continue
            self.records.extend(records)
            self.sources.extend([uploaded.name]*len(records))
        if len(self.records)>500:raise forms.ValidationError('В выбранных файлах больше 500 записей. Раздели загрузку на несколько частей.')
        if not self.records:
            raise forms.ValidationError([error['name']+': '+message for error in self.file_errors for message in error['messages']])
        return files

    @staticmethod
    def read_records(uploaded):
        if uploaded.size>5*1024*1024:raise forms.ValidationError('Файл больше 5 МБ.')
        try:data=json.loads(uploaded.read().decode('utf-8-sig'))
        except (UnicodeDecodeError,json.JSONDecodeError,RecursionError):raise forms.ValidationError('Не удалось прочитать JSON. Проверь кодировку и синтаксис файла.')
        if isinstance(data,dict):
            if 'spells' in data:data=data['spells']
            elif 'items' in data:data=data['items']
            else:data=[data]
        if not isinstance(data,list) or not data:raise forms.ValidationError('Нужен непустой список заклинаний.')
        if len(data)>500:raise forms.ValidationError('В файле больше 500 записей.')
        return data


@login_required
@require_http_methods(['GET','POST'])
def bulk_spell_import_page(request):
    if not request.user.is_staff:raise PermissionDenied
    form=BulkSpellImportForm(request.POST if request.method=='POST' else None,request.FILES if request.method=='POST' else None)
    report=None
    if request.method=='POST' and form.is_valid():
        try:
            report=import_spell_records(form.records,request.user,sources=form.sources)
            for error in form.file_errors:
                report['rows'].append({'index':len(report['rows'])+1,'name':error['name'],'source':error['name'],'status':'error','messages':error['messages'],'warnings':[]})
                report['errors']+=1
        except Exception:
            logger.exception('Bulk spell import failed; transaction rolled back')
            form.add_error(None,'Не удалось завершить импорт. Изменения этой загрузки отменены. Подробности ошибки записаны в журнал сервера.')
    return render(request,'spells/bulk_spell_import.html',{'form':form,'report':report})
