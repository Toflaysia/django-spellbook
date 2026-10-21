"""Entry point for a Windows task; SMTP settings come from the project config."""
import os
import sys
from pathlib import Path
from datetime import datetime

root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','dnd_site.settings')
logs=root/'logs';logs.mkdir(exist_ok=True)
with (logs/'email_reminders.log').open('a',encoding='utf-8') as output:
    sys.stdout=output;sys.stderr=output
    print('\n'+datetime.now().isoformat())
    from django.core.management import execute_from_command_line
    execute_from_command_line(['manage.py','send_plan_reminders'])
