import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Cria (ou redefine a senha de) um usuário administrador. Sem --password, gera uma senha aleatória.'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='admin')
        parser.add_argument('--password', default=None)
        parser.add_argument('--reset', action='store_true', help='Redefine a senha se o usuário já existir.')

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username']
        password = options['password'] or secrets.token_urlsafe(12)
        user = User.objects.filter(username=username).first()
        if user and not options['reset']:
            raise CommandError(f"O usuário '{username}' já existe. Use --reset para redefinir a senha.")
        if user is None:
            user = User(username=username)
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(f"Administrador '{username}' pronto."))
        if not options['password']:
            self.stdout.write(f'Senha gerada (anote agora, não será exibida de novo): {password}')
