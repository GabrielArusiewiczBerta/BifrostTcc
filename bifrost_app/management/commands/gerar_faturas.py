from django.core.management.base import BaseCommand
from django.utils import timezone

from bifrost_app.invoicing import generate_invoices_for_period


class Command(BaseCommand):
    help = (
        'Gera a fatura mensal simulada (com boleto fictício) de cada usuário com custo no '
        'mês informado. Sem --year/--month, usa o mês anterior ao atual — pensado pra rodar '
        'via cron todo início de mês (trabalho acadêmico, sem valor fiscal real).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, default=None)
        parser.add_argument('--month', type=int, default=None)

    def handle(self, *args, **options):
        today = timezone.now()
        year = options['year']
        month = options['month']
        if year is None or month is None:
            year, month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)

        invoices = generate_invoices_for_period(year, month)
        self.stdout.write(self.style.SUCCESS(
            f"{len(invoices)} fatura(s) gerada(s)/conferida(s) para {month:02d}/{year}."
        ))
