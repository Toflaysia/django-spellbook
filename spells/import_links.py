"""Convert imported text to safe inline tokens using existing, visible records."""
import json
import re
from collections import defaultdict
from urllib.parse import quote
from spells.description import DESCRIPTION_PREFIX, parse_description
from spells.models import Effect, DamageType, MagicSchool, SpellTime, Trait
from spells.class_access import visible_classes
from spells.spell_access import visible_spells

TOKEN = re.compile(r'\[\[(?:spell|damage|condition|school|dice|trait|effect|class|component|time):[^\n]*?\]\]')
DIE = r'\d{0,3}\s*[dDдДкКkK]\s*\d{1,4}(?:k[hl]\d{1,3})?'
DICE = re.compile(r'(?<![\w.])(?:'+DIE+r')(?:\s*[+−-]\s*(?:'+DIE+r'|\d{1,7})){0,20}(?!\w|\.\d|\s*[+−-]\s*(?:\d|[dDдДкКkK]))',re.I)
FOUNDRY_ROLL = re.compile(r'\[\[(?:/(?:r|roll)\s+)?('+DIE+r'(?:\s*[+−-]\s*(?:'+DIE+r'|\d{1,7})){0,20})\]\]',re.I)

# Foundry identifiers are external IDs, never local database primary keys.
FOUNDRY_REFERENCE = re.compile(r'@(?:Compendium|UUID)\[(?P<target>[^\]\r\n]+)\](?:\{(?P<label>[^{}\r\n]*)\})?')
INLINE_REFERENCE = re.compile(TOKEN.pattern + '|' + FOUNDRY_REFERENCE.pattern)
FOUNDRY_KINDS = {
    'spells': 'spell', 'spell': 'spell',
    'conditions': 'condition', 'condition': 'condition',
    'effects': 'effect', 'effect': 'effect',
    'classes': 'class', 'class': 'class',
    'traits': 'trait', 'feats': 'trait',
    'schools': 'school', 'damage-types': 'damage', 'casting-times': 'time',
}


def reference_names(name):
    """Keep full titles and support the common Russian [English] title format."""
    result = {name}
    match = re.fullmatch(r'(.+?)\s*\[([^\[\]]+)\]', name)
    if match:
        result.update(part.strip() for part in match.groups() if part.strip())
    return result


def key(value):
    return ' '.join(value.casefold().replace('ё','е').split())


def dice_formula(value):
    expression=re.sub(r'\s+','',value).replace('−','-')
    expression=re.sub(r'[dDдДкК]|[kK](?=\d)','d',expression).lower()
    if len(expression)>120:return None
    total=0
    for term in re.findall(r'[+-]?[^+-]+',expression):
        raw=term.lstrip('+-')
        match=re.fullmatch(r'(\d*)d(\d+)(?:k([hl])(\d+))?',raw)
        if match:
            count=int(match[1] or 1);sides=int(match[2]);keep=int(match[4] or count)
            total+=count
            if not 1<=count<=100 or not 2<=sides<=1000 or not 1<=keep<=count:return None
        elif not raw.isdigit() or int(raw)>1000000:return None
    return expression if total and total<=200 else None


def word_cases(word):
    """Conservative singular cases for common Russian catalog names."""
    lower=word.casefold()
    if lower.endswith(('ый','ой','ий')):
        stem=word[:-2]
        soft=lower.endswith('ий') and not stem.casefold().endswith(('к','г','х'))
        ends=('ий','его','ему','им','ем') if soft else (word[-2:],'ого','ому','им' if stem.casefold().endswith(('к','г','х')) else 'ым','ом')
        return [stem+x for x in ends], True
    if lower.endswith('ость'):
        return [word,word[:-1]+'и',word[:-1]+'и',word[:-1]+'ью',word[:-1]+'и'],False
    if lower.endswith('ие'):
        return [word,word[:-1]+'я',word[:-1]+'ю',word+'м',word[:-1]+'и'],False
    if lower.endswith(('ия','я')):
        return [word,word[:-1]+'и',word[:-1]+'е',word[:-1]+'ей',word[:-1]+'е'],False
    if lower.endswith('а'):
        stem=word[:-1];gen='и' if stem.casefold().endswith(tuple('гкхжчшщ')) else 'ы'
        return [word,stem+gen,stem+'е',stem+'ой',stem+'е'],False
    if lower.endswith(('ь','й')):
        stem=word[:-1];return [word,stem+'я',stem+'ю',stem+'ем',stem+'е'],False
    if lower and lower[-1] in 'бвгджзклмнпрстфхцчшщ':
        return [word,word+'а',word+'у',word+'ом',word+'е'],False
    return [word]*5,False


def aliases(name):
    words=name.split()
    if not words:return set()
    last,is_adjective=word_cases(words[-1])
    result={name}
    for index in range(1,5):
        parts=words.copy();parts[-1]=last[index]
        for n in range(len(words)-1):
            forms,adjective=word_cases(words[n])
            if adjective:parts[n]=forms[index]
        result.add(' '.join(parts))
    if is_adjective:
        stem=words[-1][:-2]
        for ending in ('ая','ой','ую','ое','ые','ых','ыми'):
            result.add(' '.join(words[:-1]+[stem+ending]))
    return result


class ImportLinker:
    def __init__(self,user):
        self.candidates=defaultdict(set)
        self.exact=defaultdict(set)
        self.warnings=set()
        self.reference_exact=defaultdict(set)
        groups=[('condition',Effect.objects.filter(category='COND'),'name'),
                ('effect',Effect.objects.exclude(category='COND'),'name'),
                ('damage',DamageType.objects.all(),'name'),('school',MagicSchool.objects.all(),'name'),
                ('trait',Trait.objects.all(),'name'),('class',visible_classes(user),'name'),
                ('time',SpellTime.objects.all(),'time'),
                ('spell',visible_spells(user),'name')]
        for kind,objects,field in groups:
            for pk,name in objects.values_list('pk',field):
                if not name or len(name)>160:continue
                item=(kind,pk)
                self.exact[key(name)].add(item)
                for title in reference_names(name):self.reference_exact[key(title)].add(item)
                for alias in aliases(name):self.candidates[key(alias)].add(item)
        patterns=[]
        for name in sorted(self.candidates,key=len,reverse=True):
            if len(name)<2:continue
            pattern=r'\s+'.join(re.escape(word).replace('е','[её]') for word in name.split())
            patterns.append(pattern)
        self.pattern=re.compile(r'(?<!\w)(?:'+'|'.join(patterns)+r')(?!\w)',re.I) if patterns else None

    def link_plain(self,text):
        def catalogs(value):
            if not self.pattern:return value
            def replace(match):
                label=match[0];normalized=key(label)
                choices=self.exact.get(normalized) or self.candidates[normalized]
                if len(choices)!=1:
                    self.warnings.add('Неоднозначная ссылка «'+label+'»: найдено несколько записей. Текст оставлен без ссылки.')
                    return label
                kind,pk=next(iter(choices))
                return f'[[{kind}:{pk}|{quote(label,safe="")}]]'
            return self.pattern.sub(replace,value)
        result=[];last=0
        for match in DICE.finditer(text):
            result.append(catalogs(text[last:match.start()]))
            expression=dice_formula(match[0])
            if expression:result.append(f'[[dice:{quote(expression,safe="")}|{quote(match[0],safe="")}]]')
            else:
                result.append(match[0]);self.warnings.add('Неподдерживаемый бросок «'+match[0]+'»: оставлен обычным текстом.')
            last=match.end()
        result.append(catalogs(text[last:]))
        return ''.join(result)

    def foundry_reference(self, match):
        label = match['label']
        if not label:
            self.warnings.add('У ссылки Foundry нет названия: внешний идентификатор удалён.')
            return ''
        choices = self.reference_exact.get(key(label)) or self.candidates.get(key(label), set())
        parts = match['target'].casefold().split('.')
        kind = next((FOUNDRY_KINDS[part] for part in reversed(parts) if part in FOUNDRY_KINDS), None)
        if kind:
            choices = {item for item in choices if item[0] == kind}
        if len(choices) == 1:
            kind, pk = next(iter(choices))
            return f'[[{kind}:{pk}|{quote(label,safe="")}]]'
        self.warnings.add('Ссылка Foundry «'+label+'»: '+('найдено несколько записей' if choices else 'запись не найдена')+'. Оставлен обычный текст.')
        return label

    def link_foundry(self, text, *, plain_links=False):
        result = []
        last = 0
        for match in INLINE_REFERENCE.finditer(text):
            between = text[last:match.start()]
            result.append(self.link_plain(between) if plain_links else between)
            result.append(self.foundry_reference(match) if match['target'] is not None else match[0])
            last = match.end()
        between = text[last:]
        result.append(self.link_plain(between) if plain_links else between)
        return ''.join(result)

    def link_text(self,text):
        def foundry(match):
            expression=dice_formula(match[1])
            return f'[[dice:{quote(expression,safe="")}|{quote(match[1],safe="")}]]' if expression else match[0]
        # Protect reference labels and IDs before applying dice detection.
        result=[];last=0
        for match in INLINE_REFERENCE.finditer(text):
            result.append(FOUNDRY_ROLL.sub(foundry,text[last:match.start()]))
            result.append(match[0]);last=match.end()
        result.append(FOUNDRY_ROLL.sub(foundry,text[last:]))
        return self.link_foundry(''.join(result), plain_links=True)

    def description(self,value,*,references_only=False):
        if len(value)>100000:raise ValueError('Описание длиннее 100 000 символов.')
        transform=self.link_foundry if references_only else self.link_text
        if not value.startswith(DESCRIPTION_PREFIX):return transform(value)
        # Preserve descriptions without Foundry markup byte-for-byte during repair.
        if references_only and not FOUNDRY_REFERENCE.search(value):return value
        blocks=parse_description(value)
        for block in blocks:
            if block['type'] in ('text','heading','quote'):block['text']=transform(block['text'])
            elif block['type']=='list':block['items']=[transform(x) for x in block['items']]
            elif block['type']=='table':block['rows']=[[transform(x) for x in row] for row in block['rows']]
        return DESCRIPTION_PREFIX+json.dumps(blocks,ensure_ascii=False)
