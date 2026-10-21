from django.core.management.base import BaseCommand,CommandError
from spells.reminders import send_due_reminders


class Command(BaseCommand):
    help='Отправить готовые почтовые напоминания. Запускать периодически.'

    def add_arguments(self,parser):
        parser.add_argument('--dry-run',action='store_true',help='Показать количество без отправки.')
        parser.add_argument('--limit',type=int,default=100)

    def handle(self,*args,**options):
        if not 1<=options['limit']<=1000:raise CommandError('limit должен быть от 1 до 1000.')
        try:result=send_due_reminders(dry_run=options['dry_run'],limit=options['limit'])
        except ValueError as error:raise CommandError(str(error))
        self.stdout.write('Готово: {due}. Отправлено: {sent}. Ошибок: {failed}.'.format(**result))
        if result['failed']:raise CommandError('Не все письма отправлены. Следующий запуск повторит попытку.')
