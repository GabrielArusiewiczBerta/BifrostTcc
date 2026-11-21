"""Geração de fatura e boleto simulados (trabalho acadêmico, sem valor fiscal real).

Cada operação cobrável (RequestLog de store/migrate bem-sucedido) só entra em UMA fatura:
ao ser faturada, ganha `RequestLog.invoice` apontando pra ela (`_generate_invoice`, numa
transação). Isso é o que permite pagar adiantado no meio do mês e, se o usuário continuar
usando a plataforma depois, gerar uma fatura nova só com o que ainda não foi cobrado — sem
duplicar cobrança nem "travar" o mês inteiro numa fatura só, como aconteceria se a fatura
fosse só "soma tudo que aconteceu nesse mês" (get_or_create por user+ano+mês).

Custo convertido de USD pra BRL por uma cotação de referência fixa — mesmo padrão de
"preço fixo, não cotação ao vivo" já usado em core_bifrost/costs.py. Número do boleto e
linha digitável têm o formato visual de um boleto real (padrão Febraban, 47 dígitos), mas
os dígitos não carregam checksum bancário de verdade: é só pra demonstrar o fluxo fim a fim
na apresentação do TCC.
"""
import calendar
import hashlib
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

USD_TO_BRL = Decimal('5.00')  # cotação de referência fixa, não ao vivo
DUE_DAY_NEXT_MONTH = 10  # vencimento: dia 10 do mês seguinte ao de referência
FAKE_BANK_CODE = '999'  # código de banco não atribuído pela Febraban, de propósito (simulação)

BILLABLE_ENDPOINTS = ('store', 'migrate')


def _next_month_date(year: int, month: int, day: int) -> date:
    y, m = (year + 1, 1) if month == 12 else (year, month + 1)
    return date(y, m, min(day, calendar.monthrange(y, m)[1]))


def _seeded_digits(seed: str, n: int) -> str:
    """Dígitos determinísticos (mesma fatura sempre gera o mesmo número), só pra parecer real."""
    h = hashlib.sha256(seed.encode()).hexdigest()
    return ''.join(str(int(c, 16) % 10) for c in h[:n])


def _format_boleto_number(invoice_id: int) -> str:
    d = _seeded_digits(f"boleto:{invoice_id}", 11)
    return f"{FAKE_BANK_CODE}-{d[:5]}.{d[5:11]}"


def _format_linha_digitavel(invoice_id: int, amount_brl: Decimal, due_date: date) -> str:
    """Formato visual de 5 blocos de uma linha digitável real (Febraban), com dígitos
    determinísticos pela fatura — não é um checksum bancário válido, é só visual."""
    d = _seeded_digits(f"linha:{invoice_id}", 29)
    fator_vencimento = str((due_date - date(1997, 10, 7)).days).zfill(4)
    valor = str(int((amount_brl * 100).to_integral_value())).zfill(10)
    campo1 = f"{FAKE_BANK_CODE}9.{d[0:5]}"
    campo2 = f"{d[5:10]}.{d[10:16]}"
    campo3 = f"{d[16:21]}.{d[21:27]}"
    dv = d[27]
    campo5 = f"{fator_vencimento}{valor}"
    return f"{campo1} {campo2} {campo3} {dv} {campo5}"


def _billable_queryset(user=None, year=None, month=None):
    """RequestLog de operações cobráveis que ainda não entraram em nenhuma fatura."""
    from .models import RequestLog

    qs = RequestLog.objects.filter(
        endpoint__in=BILLABLE_ENDPOINTS, status_code=200, invoice__isnull=True,
    ).exclude(blockchain='')
    if user is not None:
        qs = qs.filter(user=user)
    if year is not None and month is not None:
        qs = qs.filter(created_at__year=year, created_at__month=month)
    return qs


def _generate_invoice(user, logs_qs, year: int, month: int):
    """Fatura exatamente as linhas de `logs_qs` (já filtradas por ainda não faturadas) e
    marca cada uma com `invoice` pra nunca entrar em outra fatura depois. Devolve None se
    não há custo a cobrar."""
    from .models import Invoice, RequestLog

    with transaction.atomic():
        logs = list(logs_qs.select_for_update())
        cost_usd = sum(log.cost_usd for log in logs)
        amount_brl = (Decimal(str(cost_usd)) * USD_TO_BRL).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if amount_brl <= 0:
            return None

        due_date = _next_month_date(year, month, DUE_DAY_NEXT_MONTH)
        invoice = Invoice.objects.create(
            user=user, year=year, month=month, amount_brl=amount_brl, due_date=due_date,
            boleto_number='', linha_digitavel='',
        )
        invoice.boleto_number = _format_boleto_number(invoice.pk)
        invoice.linha_digitavel = _format_linha_digitavel(invoice.pk, amount_brl, due_date)
        invoice.save(update_fields=['boleto_number', 'linha_digitavel'])
        RequestLog.objects.filter(pk__in=[log.pk for log in logs]).update(invoice=invoice)
    return invoice


def generate_invoice_for_user(user, year: int, month: int):
    """Fatura agora tudo que esse usuário ainda não tiver pago no mês/ano informado — usada
    pelo botão de autosserviço "pagar fatura antecipada". Pode gerar mais de uma fatura no
    mesmo mês se ele continuar usando a plataforma depois: cada uma cobre só o que ainda não
    tinha sido cobrado, nunca a mesma operação duas vezes. Devolve None se não há nada a cobrar."""
    return _generate_invoice(user, _billable_queryset(user=user, year=year, month=month), year, month)


def invoice_items(invoice):
    """Uma linha por operação faturada (hash + valor em BRL), pra detalhar o boleto. O valor de
    cada item é arredondado separadamente, então a soma pode diferir em poucos centavos do total
    da fatura (que é arredondado uma vez só, sobre a soma em USD) — comportamento normal de
    detalhamento de fatura, não é bug."""
    return [
        {
            'tx_hash': log.tx_hash,
            'blockchain': log.blockchain,
            'amount_brl': (Decimal(str(log.cost_usd)) * USD_TO_BRL).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        }
        for log in invoice.items.order_by('created_at')
    ]


def generate_invoices_for_period(year: int, month: int):
    """Fecha o mês/ano informado: fatura, para cada usuário, o que ainda não tiver sido
    faturado nesse período (o que sobrou depois de eventuais faturas antecipadas — se o
    usuário já pagou tudo adiantado, não gera nada de novo). Devolve as Invoice criadas
    nesta chamada."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user_ids = _billable_queryset(year=year, month=month).values_list('user', flat=True).distinct()
    invoices = []
    for user in User.objects.filter(pk__in=list(user_ids)):
        invoice = generate_invoice_for_user(user, year, month)
        if invoice is not None:
            invoices.append(invoice)
    return invoices
