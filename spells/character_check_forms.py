from spells.training_widgets import TrainingCircles
from copy import deepcopy
from django import forms
from spells.character_checks import ABILITIES, SKILLS, SPEEDS, PASSIVES, TRAINING, FACTORS


class CharacterChecksFormMixin:
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        config=self.instance.check_settings or {}
        self.check_groups=[]
        self.fields['checks_present']=forms.BooleanField(required=False,initial=True,widget=forms.HiddenInput)
        def number(name,label,value=0,help_text='',minimum=-1000,maximum=1000):
            self.fields[name]=forms.IntegerField(label=label,initial=value,required=False,min_value=minimum,max_value=maximum,help_text=help_text)
            return name
        def choice(name,label,value,choices):
            if name.endswith("_training"):
                order=("none","proficient","expertise","half")
                choices=sorted(choices,key=lambda item:order.index(item[0]))
            self.fields[name]=forms.ChoiceField(label=label,initial=value,choices=choices,required=False,widget=TrainingCircles if name.endswith('_training') else forms.Select)
            return name
        def checkbox(name,label,value=False):
            self.fields[name]=forms.BooleanField(label=label,initial=value,required=False)
            return name
        def row(kind,key,title,fields,ability=''):
            return {'kind':kind,'key':key,'title':title,'ability':ability,'fields':[self[f] for f in fields]}
        general=[number('checks_proficiency_override','Бонус мастерства вручную',config.get('proficiency_override'),'Оставь пустым для расчёта от общего уровня персонажа.',0,20),
                 number('checks_initiative_bonus','Дополнительный бонус инициативы',self.instance.initiative_bonus),
                 checkbox('checks_initiative_half','Половина мастерства к инициативе',config.get('initiative_half',False))]
        self.check_groups.append({'id':'derived','title':'Расчёты','rows':[row('general','initiative','Инициатива и мастерство',general)]})
        for group,items,title in [('skills',SKILLS,'Навыки'),('saves',[(k,v,k) for k,v in ABILITIES.items()],'Спасброски')]:
            rows=[]
            for key,label,ability in items:
                setting=config.get(group,{}).get(key,{})
                prefix=f'checks_{group}_{key}'
                fields=[choice(prefix+'_training','Владение',setting.get('training','none'),TRAINING if group=='skills' else (TRAINING[0],TRAINING[2])),number(prefix+'_bonus','Дополнительный бонус',setting.get('bonus',0))]
                rows.append(row(group,key,label,fields,ABILITIES[ability]))
            self.check_groups.append({'id':group,'title':title,'rows':rows})
        rows=[]
        for key in PASSIVES:
            label=next(label for name,label,_ in SKILLS if name==key)
            setting=config.get('passives',{}).get(key,{})
            prefix=f'checks_passives_{key}'
            rows.append(row('passives',key,label,[number(prefix+'_bonus','Бонус только к пассивному значению',setting.get('bonus',0)),checkbox(prefix+'_advantage','Преимущество (+5)',setting.get('advantage',False)),checkbox(prefix+'_disadvantage','Помеха (−5)',setting.get('disadvantage',False))]))
        self.check_groups.append({'id':'passives','title':'Пассивные значения','rows':rows})
        rows=[]
        for key,label in SPEEDS.items():
            setting=config.get('speeds',{}).get(key,{})
            prefix=f'checks_speeds_{key}'
            fields=[] if key=='walk' else [number(prefix+'_base','Базовая скорость, футы',setting.get('base',0),minimum=0,maximum=10000)]
            fields += [number(prefix+'_bonus','Дополнительная скорость, футы',setting.get('bonus',0)),choice(prefix+'_factor','Изменение скорости',setting.get('factor','normal'),FACTORS)]
            rows.append(row('speeds',key,label,fields))
        self.check_groups.append({'id':'speeds','title':'Передвижение','rows':rows})

    @property
    def check_data(self):
        return {'skills':SKILLS,'abilities':ABILITIES,'speeds':SPEEDS,'extra_levels':self.instance.second_class_level+self.instance.warlock_level,'skill_settings':(self.instance.check_settings or {}).get('skills',{})}

    def save(self,commit=True):
        if self.errors:raise ValueError('Нельзя сохранить форму с ошибками.')
        if self.cleaned_data.get('checks_present'):
            data=self.cleaned_data
            config=deepcopy(self.instance.check_settings or {})
            config['proficiency_override']=data.get('checks_proficiency_override')
            config['initiative_half']=data.get('checks_initiative_half',False)
            self.instance.initiative_bonus=data.get('checks_initiative_bonus') or 0
            for group,keys in [('skills',[x[0] for x in SKILLS]),('saves',list(ABILITIES)),('passives',list(PASSIVES)),('speeds',list(SPEEDS))]:
                if group == 'skills' and not any(
                    self.add_prefix(f'checks_skills_{key}_{part}') in self.data
                    for key in keys for part in ('training','bonus')
                ):
                    continue
                config[group]={}
                for key in keys:
                    prefix=f'checks_{group}_{key}'
                    item={'bonus':data.get(prefix+'_bonus') or 0}
                    if group in ('skills','saves'):item['training']=data.get(prefix+'_training') or 'none'
                    if group=='passives':item.update({k:data.get(prefix+'_'+k,False) for k in ('advantage','disadvantage')})
                    if group=='speeds':
                        item['factor']=data.get(prefix+'_factor') or 'normal'
                        if key!='walk':item['base']=data.get(prefix+'_base') or 0
                    config[group][key]=item
            self.instance.check_settings=config
        return super().save(commit=commit)
