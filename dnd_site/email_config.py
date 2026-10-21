"""Load optional local SMTP settings; credentials stay outside version control."""
import json
import os
from urllib.parse import urlsplit
from django.core.exceptions import ImproperlyConfigured


def configure_email(base_dir):
    path=base_dir/'email_settings.json'
    values={}
    if path.is_file():
        try:
            values=json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(values,dict):raise ValueError()
        except (ValueError,OSError):raise ImproperlyConfigured('Проверь формат email_settings.json.')
    def get(name,default=''):
        return os.environ.get('SPELLBOOK_EMAIL_'+name.upper(),values.get(name,default))
    def boolean(name,default):
        value=get(name,default)
        if isinstance(value,bool):return value
        if str(value).lower() in ('true','1','yes'):return True
        if str(value).lower() in ('false','0','no'):return False
        raise ImproperlyConfigured('Неверное логическое значение настройки почты: '+name)
    host=get('host')
    site=get('site_url','http://127.0.0.1:8000').rstrip('/')
    parsed=urlsplit(site)
    if parsed.scheme not in ('http','https') or not parsed.netloc or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ImproperlyConfigured('В site_url нужен адрес сайта, например http://127.0.0.1:8000.')
    tls=boolean('use_tls',True);ssl=boolean('use_ssl',False)
    if tls and ssl:raise ImproperlyConfigured('Выбери use_tls или use_ssl, одновременно включать их нельзя.')
    try:port=int(get('port',587))
    except (TypeError,ValueError):raise ImproperlyConfigured('port должен быть числом.')
    if not 1<=port<=65535:raise ImproperlyConfigured('Недопустимый порт почтового сервера.')
    sender=get('from_email') or get('username')
    return {'EMAIL_BACKEND':'django.core.mail.backends.smtp.EmailBackend' if host else 'django.core.mail.backends.console.EmailBackend',
            'EMAIL_HOST':host,'EMAIL_PORT':port,'EMAIL_HOST_USER':get('username'),'EMAIL_HOST_PASSWORD':get('password'),
            'EMAIL_USE_TLS':tls,'EMAIL_USE_SSL':ssl,'EMAIL_TIMEOUT':20,'DEFAULT_FROM_EMAIL':sender or 'noreply@localhost',
            'SPELLBOOK_EMAIL_DELIVERY_ENABLED':bool(host and sender),'SPELLBOOK_SITE_URL':site}


def project_secret_key(base_dir):
    value=os.environ.get('SPELLBOOK_SECRET_KEY')
    if value:return value
    path=base_dir/'secret_key.txt'
    if not path.exists():
        from django.core.management.utils import get_random_secret_key
        try:
            descriptor=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor,'w',encoding='utf-8') as output:
                output.write(get_random_secret_key())
    value=path.read_text(encoding='utf-8').strip()
    if len(value)<40:raise ImproperlyConfigured('Проверь secret_key.txt: нужен постоянный секретный ключ приложения.')
    return value
