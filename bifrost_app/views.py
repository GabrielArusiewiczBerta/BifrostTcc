import datetime
import functools
import hashlib
import json
import logging
import secrets

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Count, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

import core_bifrost.api as bifrost_api
import core_bifrost.costs as bifrost_costs
import core_bifrost.db_manager as bifrost_db
import core_bifrost.net as bifrost_net
from core_bifrost.blockchain import Blockchain
from core_bifrost.custom_errors import (
    TransactionSizeError, TransactionNotFoundError, BlockchainNotFoundError, DecryptionError,
)

from .context_processors import REAL_CAPABLE_NETWORKS
from .invoicing import generate_invoice_for_user, generate_invoices_for_period, invoice_items
from .models import ApiKey, NetworkCredential, RequestLog, UserBlockchainKey
from .server_secrets import encrypt_secret

logger = logging.getLogger(__name__)

BLOCKCHAIN_METADATA = [
    {'code': 'RBB', 'name': 'Rede Blockchain Brasil', 'icon': 'fa-shield-halved', 'badge': 'emerald', 'type': 'Permissionada (Hyperledger Besu)', 'max_size': '512 bytes', 'status': 'Simulado'},
    {'code': 'BITCOIN', 'name': 'Bitcoin Testnet', 'icon': 'fa-bitcoin', 'badge': 'amber', 'type': 'Pública (OP_RETURN)', 'max_size': '80 bytes', 'status': 'Simulado'},
    {'code': 'ETHEREUM', 'name': 'Ethereum Sepolia', 'icon': 'fa-ethereum', 'badge': 'indigo', 'type': 'Pública (Calldata / Smart Contract)', 'max_size': '1024 bytes', 'status': 'Simulado'},
    {'code': 'STELLAR', 'name': 'Stellar Testnet', 'icon': 'fa-rocket', 'badge': 'cyan', 'type': 'Pública (Memo_Text)', 'max_size': '28 bytes', 'status': 'Simulado'},
    {'code': 'EOS', 'name': 'EOS Jungle', 'icon': 'fa-bolt', 'badge': 'purple', 'type': 'Pública (Action Memo)', 'max_size': '256 bytes', 'status': 'Simulado'},
    {'code': 'POSTGRES', 'name': 'PostgreSQL Mirror', 'icon': 'fa-database', 'badge': 'blue', 'type': 'Banco Relacional de Redundância', 'max_size': '4096 bytes', 'status': 'Simulado'},
    {'code': 'MULTICHAIN', 'name': 'MultiChain Private', 'icon': 'fa-link', 'badge': 'rose', 'type': 'Privada (Streams)', 'max_size': '512 bytes', 'status': 'Simulado'},
]

USER_ERRORS = (TransactionSizeError, BlockchainNotFoundError, ValueError)


def _log_request(user, source, endpoint, method, status_code, blockchain='', cost=None, tx_hash=''):
    cost = cost or {}
    RequestLog.objects.create(
        user=user, source=source, endpoint=endpoint, method=method,
        status_code=status_code, blockchain=str(blockchain or '')[:20],
        tx_hash=str(tx_hash or '')[:80] if status_code == 200 else '',
        tx_count=cost.get('fragments', 0) if status_code == 200 else 0,
        bytes_stored=cost.get('onchain_bytes', 0) if status_code == 200 else 0,
        fee_native=cost.get('fee_native', 0.0) if status_code == 200 else 0.0,
        cost_usd=cost.get('fee_usd', 0.0) if status_code == 200 else 0.0,
    )


def _estimate_or_none(blockchain, payload, encrypted):
    """Custo estimado da operação para a contabilidade; nunca deve quebrar a operação em si."""
    try:
        return bifrost_costs.estimate(blockchain, payload=payload, encrypted=encrypted, multiple_tx=True)
    except Exception:
        logger.exception('Falha ao estimar custo')
        return None


def staff_required(view):
    @login_required
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


def _blockchains_with_status():
    result = []
    for bc in BLOCKCHAIN_METADATA:
        bc = dict(bc)
        bc['status'] = 'Real (Testnet)' if bifrost_net.real_network_enabled(bc['code']) else 'Simulado'
        result.append(bc)
    return result


def get_context_base(request, active_tab='dashboard'):
    txs = bifrost_db.get_all_transactions(owner=request.user.pk)
    return {
        'active_tab': active_tab,
        'blockchains': _blockchains_with_status(),
        'total_transactions': len(txs),
        'active_nodes_count': len(BLOCKCHAIN_METADATA),
        'total_requests': request.user.request_logs.count(),
        'recent_transactions': txs[:5],
        'all_transactions': txs,
    }


# Autenticação

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Conta criada. Bem-vindo ao NodeConnect!')
        return redirect('dashboard')
    return render(request, 'register.html', {'form': form})


def _account_context(request):
    ctx = get_context_base(request, 'account')
    logs = request.user.request_logs
    ctx['api_key'] = ApiKey.objects.filter(user=request.user).first()
    ctx['usage_by_endpoint'] = list(
        logs.values('source', 'endpoint').annotate(total=Count('id')).order_by('-total')
    )
    ctx['recent_requests'] = logs.all()[:15]
    return ctx


@login_required
def account_view(request):
    return render(request, 'account.html', _account_context(request))


@login_required
@require_POST
def generate_api_key_view(request):
    raw_key = 'bfr_' + secrets.token_urlsafe(32)
    ApiKey.objects.update_or_create(
        user=request.user,
        defaults={
            'key_hash': hashlib.sha256(raw_key.encode()).hexdigest(),
            'prefix': raw_key[:12],
            'last_used_at': None,
            'expires_at': timezone.now() + ApiKey.VALIDITY,
        },
    )
    ctx = _account_context(request)
    ctx['new_api_key'] = raw_key
    return render(request, 'account.html', ctx)


@login_required
@require_POST
def renew_api_key_view(request):
    """Estende a validade da chave atual por mais 1h, sem trocar o valor (não expõe a chave de novo)."""
    updated = ApiKey.objects.filter(user=request.user).update(expires_at=timezone.now() + ApiKey.VALIDITY)
    if updated:
        messages.success(request, 'Validade da chave renovada por mais 1 hora.')
    else:
        messages.error(request, 'Nenhuma chave de API para renovar.')
    return render(request, 'account.html', _account_context(request))


@login_required
@require_POST
def revoke_api_key_view(request):
    ApiKey.objects.filter(user=request.user).delete()
    messages.success(request, 'Chave de API revogada.')
    return render(request, 'account.html', _account_context(request))


# Interface web

@login_required
def dashboard_view(request):
    return render(request, 'dashboard.html', get_context_base(request, 'dashboard'))


@login_required
def store_view(request):
    ctx = get_context_base(request, 'store')

    if request.method == 'POST':
        payload = request.POST.get('payload', '').strip()
        blockchain_code = request.POST.get('blockchain', 'RBB')
        password = request.POST.get('password', '').strip() or None
        multiple_tx = request.POST.get('multiple_tx') == 'on'
        redundancy = request.POST.get('redundancy') == 'on'

        if not payload:
            messages.error(request, 'Por favor, insira o conteúdo/dado que deseja armazenar.')
            return render(request, 'store.html', ctx)

        status = 200
        cost = None
        hashes = []
        try:
            hashes = bifrost_api.store(
                text=payload, blockchain=blockchain_code, pw=password,
                multiple_tx=multiple_tx, redundancy=redundancy, owner=request.user.pk,
            )
            cost = _estimate_or_none(blockchain_code, payload, bool(password))
            ctx['success_result'] = {
                'hashes': hashes,
                'blockchain': blockchain_code,
                'payload_preview': payload[:80],
                'encrypted': bool(password),
                'count': len(hashes),
                'cost': cost,
            }
            messages.success(request, f'Sucesso! {len(hashes)} transação(ões) gravada(s) na blockchain {blockchain_code}.')
        except USER_ERRORS as err:
            status = 400
            messages.error(request, str(err))
        except Exception:
            status = 500
            logger.exception('Falha em store')
            messages.error(request, 'Não foi possível armazenar os dados. Verifique a rede escolhida e tente novamente.')
        _log_request(request.user, 'web', 'store', 'POST', status, blockchain_code, cost, tx_hash=hashes[0] if hashes else '')
        ctx.update(get_context_base(request, 'store'))

    return render(request, 'store.html', ctx)


@login_required
@require_POST
def store_start_view(request):
    """Prepara os fragmentos e devolve o total, para a barra de progresso acompanhar a gravação real (FR10)."""
    try:
        data = _json_body(request)
        payload = (data.get('payload') or '').strip()
        blockchain = data.get('blockchain', 'RBB')
        if not payload:
            raise ValueError('Informe o conteúdo a armazenar.')
        job = bifrost_api.prepare_store(
            payload, blockchain, pw=data.get('password') or None,
            multiple_tx=bool(data.get('multiple_tx')), redundancy=bool(data.get('redundancy')),
        )
        request.session['store_job'] = job
        request.session['store_job_meta'] = {'blockchain': blockchain, 'payload_preview': payload[:80]}
        return JsonResponse({'status': 'success', 'total': job['total']})
    except USER_ERRORS as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except Exception:
        logger.exception('Falha ao iniciar store incremental')
        return JsonResponse({'status': 'error', 'message': 'Não foi possível iniciar a operação.'}, status=500)


@login_required
@require_POST
def store_step_view(request):
    """Grava um único fragmento do job em andamento e informa o progresso."""
    job = request.session.get('store_job')
    if not job:
        return JsonResponse({'status': 'error', 'message': 'Nenhuma operação em andamento. Recarregue e tente novamente.'}, status=400)

    try:
        job, finished, hashes = bifrost_api.run_store_step(job, owner=request.user.pk)
    except Exception:
        request.session.pop('store_job', None)
        request.session.pop('store_job_meta', None)
        logger.exception('Falha ao gravar fragmento')
        return JsonResponse({'status': 'error', 'message': 'Falha ao gravar um fragmento. Tente novamente.'}, status=500)

    progress = sum(len(c['done']) for c in job['chains'])

    if not finished:
        request.session['store_job'] = job
        return JsonResponse({
            'status': 'success', 'done': False, 'progress': progress, 'total': job['total'],
            'blockchain': job['chains'][job['chain_idx']]['blockchain'],
        })

    meta = request.session.pop('store_job_meta', {})
    request.session.pop('store_job', None)
    blockchain_code = meta.get('blockchain', '')
    cost = None
    try:
        cost = bifrost_costs.estimate(blockchain_code, size_bytes=job['raw_bytes'], encrypted=job['encrypted'], multiple_tx=True)
    except Exception:
        logger.exception('Falha ao estimar custo')
    _log_request(request.user, 'web', 'store', 'POST', 200, blockchain_code, cost, tx_hash=hashes[0] if hashes else '')

    return JsonResponse({
        'status': 'success', 'done': True, 'progress': progress, 'total': job['total'],
        'hashes': hashes, 'blockchain': blockchain_code, 'payload_preview': meta.get('payload_preview', ''),
        'encrypted': job['encrypted'], 'count': len(hashes), 'cost': _cost_summary(cost),
    })


@login_required
def retrieve_view(request):
    ctx = get_context_base(request, 'retrieve')
    tx_hash = (request.GET.get('hash', '') or request.POST.get('hash', '')).strip()
    password = request.POST.get('password', '') or None

    ctx['input_hash'] = tx_hash

    if tx_hash:
        status = 200
        try:
            result = bifrost_api.retrieve(tx_hash, pw=password, owner=request.user.pk)
            ctx['retrieved_result'] = result
            messages.success(request, 'Transação localizada e processada com sucesso!')
        except TransactionNotFoundError as err:
            status = 404
            messages.error(request, f'Transação não encontrada: {str(err)}')
        except DecryptionError as err:
            status = 403
            messages.error(request, str(err))
        except Exception:
            status = 500
            logger.exception('Falha em retrieve')
            messages.error(request, 'Não foi possível recuperar os dados. Verifique o hash e a senha.')
        _log_request(request.user, 'web', 'retrieve', request.method, status)
        ctx.update(get_context_base(request, 'retrieve'))

    return render(request, 'retrieve.html', ctx)


@login_required
def migrate_view(request):
    ctx = get_context_base(request, 'migrate')

    if request.method == 'POST':
        source_hash = request.POST.get('source_hash', '').strip()
        target_blockchain = request.POST.get('target_blockchain', 'ETHEREUM')
        multiple_tx = request.POST.get('multiple_tx') == 'on'

        if not source_hash:
            messages.error(request, 'Forneça o Hash de transação de origem.')
            return render(request, 'migrate.html', ctx)

        status = 200
        cost = None
        result = None
        try:
            result = bifrost_api.migrate(source_hash, target_blockchain, multiple_tx=multiple_tx, owner=request.user.pk)
            cost = _estimate_or_none(target_blockchain, result['payload_migrated'], False)
            ctx['migration_result'] = result
            messages.success(request, f'Dados migrados com sucesso para a blockchain {target_blockchain}!')
        except TransactionNotFoundError as err:
            status = 404
            messages.error(request, str(err))
        except USER_ERRORS as err:
            status = 400
            messages.error(request, str(err))
        except Exception:
            status = 500
            logger.exception('Falha em migrate')
            messages.error(request, 'Não foi possível migrar os dados. Verifique o hash de origem e a rede de destino.')
        tx_hash = result['new_hashes'][0] if result and result.get('new_hashes') else ''
        _log_request(request.user, 'web', 'migrate', 'POST', status, target_blockchain, cost, tx_hash=tx_hash)
        ctx.update(get_context_base(request, 'migrate'))

    return render(request, 'migrate.html', ctx)


@login_required
@require_POST
def migrate_start_view(request):
    """Recupera o payload de origem e prepara os fragmentos de destino, para a barra de progresso
    acompanhar a migração real (FR10)."""
    try:
        data = _json_body(request)
        source_hash = (data.get('source_hash') or '').strip()
        target = data.get('target_blockchain', 'ETHEREUM')
        if not source_hash:
            raise ValueError('Forneça o Hash de transação de origem.')
        job = bifrost_api.prepare_migrate(
            source_hash, target, multiple_tx=bool(data.get('multiple_tx')), owner=request.user.pk,
        )
        request.session['migrate_job'] = job
        return JsonResponse({'status': 'success', 'total': job['total']})
    except TransactionNotFoundError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=404)
    except USER_ERRORS as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except Exception:
        logger.exception('Falha ao iniciar migrate incremental')
        return JsonResponse({'status': 'error', 'message': 'Não foi possível iniciar a migração.'}, status=500)


@login_required
@require_POST
def migrate_step_view(request):
    """Grava um único fragmento da migração em andamento e informa o progresso."""
    job = request.session.get('migrate_job')
    if not job:
        return JsonResponse({'status': 'error', 'message': 'Nenhuma operação em andamento. Recarregue e tente novamente.'}, status=400)

    try:
        job, finished, hashes = bifrost_api.run_store_step(job, owner=request.user.pk)
    except Exception:
        request.session.pop('migrate_job', None)
        logger.exception('Falha ao gravar fragmento de migração')
        return JsonResponse({'status': 'error', 'message': 'Falha ao gravar um fragmento. Tente novamente.'}, status=500)

    progress = sum(len(c['done']) for c in job['chains'])

    if not finished:
        request.session['migrate_job'] = job
        return JsonResponse({'status': 'success', 'done': False, 'progress': progress, 'total': job['total']})

    request.session.pop('migrate_job', None)
    target_blockchain = job['chains'][0]['blockchain']
    cost = None
    try:
        cost = bifrost_costs.estimate(target_blockchain, size_bytes=job['raw_bytes'], encrypted=False, multiple_tx=True)
    except Exception:
        logger.exception('Falha ao estimar custo')
    _log_request(request.user, 'web', 'migrate', 'POST', 200, target_blockchain, cost, tx_hash=hashes[0] if hashes else '')

    return JsonResponse({
        'status': 'success', 'done': True, 'progress': progress, 'total': job['total'],
        'new_hashes': hashes, 'source_hash': job['source_hash'], 'source_blockchain': job['source_blockchain'],
        'target_blockchain': target_blockchain, 'payload_migrated': job['payload'],
    })


@login_required
def explorer_view(request):
    return render(request, 'explorer.html', get_context_base(request, 'explorer'))


def api_docs_view(request):
    """Documentação interativa da API REST (Swagger UI sobre static/openapi.yaml). Pública,
    sem exigir login, já que a API é consumida por sistemas externos (UC08)."""
    return render(request, 'api_docs.html')


@login_required
def billing_view(request):
    """Histórico consolidado de custo simulado do próprio usuário, filtrável por blockchain e período (UC10/FR17)."""
    period = request.GET.get('period', '30')
    if period not in PERIODS:
        period = '30'
    blockchain = request.GET.get('blockchain', '').strip().upper()
    if blockchain not in VALID_BLOCKCHAIN_CODES:
        blockchain = ''

    logs = request.user.request_logs.all()
    if PERIODS[period]:
        logs = logs.filter(created_at__gte=timezone.now() - datetime.timedelta(days=PERIODS[period]))
    spending = logs.filter(endpoint__in=('store', 'migrate'), status_code=200).exclude(blockchain='')
    if blockchain:
        spending = spending.filter(blockchain=blockchain)

    chains = list(
        spending.values('blockchain').annotate(
            cost=Sum('cost_usd'), txs=Sum('tx_count'), volume=Sum('bytes_stored'),
            native=Sum('fee_native'), ops=Count('id'),
        ).order_by('-cost')
    )
    top_cost = max((c['cost'] or 0 for c in chains), default=0)
    for row in chains:
        row['symbol'] = bifrost_costs.symbol_for(row['blockchain'])
        row['bar'] = round(100 * (row['cost'] or 0) / top_cost) if top_cost else 0

    totals = spending.aggregate(cost=Sum('cost_usd'), txs=Sum('tx_count'), volume=Sum('bytes_stored'))
    ctx = get_context_base(request, 'billing')
    ctx.update({
        'chains': chains,
        'totals': totals,
        'operations': spending.order_by('-created_at')[:30],
        'period': period,
        'blockchain': blockchain,
        'periods': [('7', '7 dias'), ('30', '30 dias'), ('90', '90 dias'), ('all', 'Tudo')],
        'invoices': request.user.invoices.all()[:12],
    })
    return render(request, 'billing.html', ctx)


@login_required
def invoice_boleto_view(request, pk):
    invoice = request.user.invoices.filter(pk=pk).first()
    if invoice is None:
        raise Http404('Fatura não encontrada.')
    return render(request, 'invoice_boleto.html', {'invoice': invoice, 'active_tab': 'billing'})


@login_required
def invoice_boleto_pdf_view(request, pk):
    from io import BytesIO

    from django.template.loader import render_to_string
    from xhtml2pdf import pisa

    invoice = request.user.invoices.filter(pk=pk).first()
    if invoice is None:
        raise Http404('Fatura não encontrada.')

    html = render_to_string('invoice_boleto_pdf.html', {'invoice': invoice, 'items': invoice_items(invoice)})
    buffer = BytesIO()
    pisa.CreatePDF(html, dest=buffer)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="fatura_{invoice.month:02d}_{invoice.year}.pdf"'
    return response


@login_required
@require_POST
def invoice_pay_advance_view(request):
    """Autosserviço: gera (se ainda não existir) a fatura do mês corrente com o custo
    acumulado até agora e já marca como paga, sem esperar o início do mês seguinte."""
    today = timezone.now()
    invoice = generate_invoice_for_user(request.user, today.year, today.month)
    if invoice is None:
        messages.error(request, 'Você ainda não tem custo registrado neste mês para antecipar.')
        return redirect('billing')
    if invoice.status != 'pago':
        invoice.status = 'pago'
        invoice.save(update_fields=['status'])
    messages.success(request, f'Fatura de {today.month:02d}/{today.year} antecipada e paga (simulado): R$ {invoice.amount_brl}.')
    return redirect('invoice_boleto', pk=invoice.pk)


@login_required
@require_POST
def invoice_mark_paid_view(request, pk):
    invoice = request.user.invoices.filter(pk=pk).first()
    if invoice is None:
        raise Http404('Fatura não encontrada.')
    invoice.status = 'pago'
    invoice.save(update_fields=['status'])
    messages.success(request, 'Fatura marcada como paga (simulado).')
    return redirect('invoice_boleto', pk=pk)


@staff_required
@require_POST
def admin_generate_invoices_view(request):
    """Gera agora as faturas do mês atual, sem esperar o cron (demonstração/TCC)."""
    today = timezone.now()
    invoices = generate_invoices_for_period(today.year, today.month)
    messages.success(request, f'{len(invoices)} fatura(s) gerada(s)/conferida(s) para {today.month:02d}/{today.year}.')
    return redirect('admin_accounting')


# Carteira (Wallet) — credenciais de acesso por rede, UC05/FR11

VALID_BLOCKCHAIN_CODES = {b['code'] for b in BLOCKCHAIN_METADATA}


@login_required
def wallet_view(request):
    ctx = get_context_base(request, 'wallet')

    if request.method == 'POST':
        blockchain = request.POST.get('blockchain', '').strip().upper()
        label = request.POST.get('label', '').strip()
        external_id = request.POST.get('external_id', '').strip()

        if blockchain not in VALID_BLOCKCHAIN_CODES:
            messages.error(request, 'Selecione uma blockchain suportada.')
        elif not label:
            messages.error(request, 'Informe um rótulo para a credencial.')
        else:
            NetworkCredential.objects.create(
                user=request.user, blockchain=blockchain, label=label, external_id=external_id,
            )
            messages.success(request, 'Credencial adicionada.')
            return redirect('wallet')

    ctx['credentials'] = request.user.network_credentials.all()
    own_keys = {k.blockchain: k for k in request.user.blockchain_keys.all()}
    ctx['own_key_rows'] = [{'code': code, 'key': own_keys.get(code)} for code in REAL_CAPABLE_NETWORKS]
    return render(request, 'wallet.html', ctx)


@login_required
@require_POST
def wallet_generate_key_view(request, blockchain):
    blockchain = blockchain.upper()
    if blockchain not in REAL_CAPABLE_NETWORKS:
        messages.error(request, 'Essa blockchain não suporta chave própria.')
        return redirect('wallet')

    if blockchain == 'STELLAR':
        from core_bifrost.testnet_keys import generate_stellar_keypair
        keypair = generate_stellar_keypair()
        public_address, raw_secret = keypair.public_key, keypair.secret
    elif blockchain == 'BITCOIN':
        from core_bifrost.testnet_keys import generate_btc_key
        private_key = generate_btc_key()
        public_address = private_key.get_public_key().get_segwit_address().to_string()
        raw_secret = private_key.to_wif()
    else:  # ETHEREUM
        from core_bifrost.testnet_keys import generate_eth_account
        account = generate_eth_account()
        public_address, raw_secret = account.address, account.key.hex()

    UserBlockchainKey.objects.update_or_create(
        user=request.user, blockchain=blockchain,
        defaults={'public_address': public_address, 'encrypted_secret': encrypt_secret(raw_secret)},
    )
    messages.success(
        request,
        f'Chave própria gerada para {blockchain} (endereço {public_address}). '
        f'Lembre-se de financiá-la via faucet de testnet antes de usar — ela começa sem saldo.',
    )
    return redirect('wallet')


@login_required
@require_POST
def wallet_delete_key_view(request, blockchain):
    deleted, _ = request.user.blockchain_keys.filter(blockchain=blockchain.upper()).delete()
    if deleted:
        messages.success(request, 'Chave própria removida. Essa blockchain volta a usar a chave central.')
    return redirect('wallet')


@login_required
@require_POST
def wallet_credential_rename(request, pk):
    credential = request.user.network_credentials.filter(pk=pk).first()
    label = request.POST.get('label', '').strip()
    if credential and label:
        credential.label = label
        credential.external_id = request.POST.get('external_id', '').strip()
        credential.save(update_fields=['label', 'external_id'])
        messages.success(request, 'Credencial atualizada.')
    else:
        messages.error(request, 'Não foi possível atualizar a credencial.')
    return redirect('wallet')


@login_required
@require_POST
def wallet_credential_delete(request, pk):
    deleted, _ = request.user.network_credentials.filter(pk=pk).delete()
    if deleted:
        messages.success(request, 'Credencial removida.')
    return redirect('wallet')


# API REST (autenticada por chave: Authorization: Bearer <chave>)

def _json_body(request):
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        raise ValueError('Corpo da requisição deve ser um JSON válido.')
    if not isinstance(data, dict):
        raise ValueError('Corpo da requisição deve ser um objeto JSON.')
    return data


def _api_error(exc):
    if isinstance(exc, TransactionNotFoundError):
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=404)
    if isinstance(exc, DecryptionError):
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=403)
    if isinstance(exc, USER_ERRORS):
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)
    logger.exception('Erro inesperado na API')
    return JsonResponse({'status': 'error', 'message': 'Erro interno do servidor.'}, status=500)


def api_endpoint(name, methods):
    """Exige chave de API válida, restringe métodos e contabiliza a requisição."""
    def decorator(view):
        @csrf_exempt
        @functools.wraps(view)
        def wrapper(request):
            header = request.headers.get('Authorization', '')
            raw_key = header[7:].strip() if header.lower().startswith('bearer ') else ''
            api_key = None
            if raw_key:
                api_key = ApiKey.objects.select_related('user').filter(
                    key_hash=hashlib.sha256(raw_key.encode()).hexdigest(), user__is_active=True,
                ).first()
            if api_key is None:
                return JsonResponse(
                    {'status': 'error', 'message': 'Chave de API ausente ou inválida. Use Authorization: Bearer <chave>.'},
                    status=401,
                )
            if api_key.is_expired:
                return JsonResponse(
                    {'status': 'error', 'message': 'Chave de API expirada. Gere ou renove em /account/.'},
                    status=401,
                )
            request.api_user = api_key.user
            ApiKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())

            if request.method not in methods:
                response = JsonResponse({'error': f"Método não permitido. Use {' ou '.join(methods)}."}, status=405)
            else:
                response = view(request)
            _log_request(request.api_user, 'api', name, request.method, response.status_code,
                         getattr(request, 'log_blockchain', ''), getattr(request, 'log_cost', None),
                         tx_hash=getattr(request, 'log_hash', ''))
            return response
        return wrapper
    return decorator


@api_endpoint('store', ('POST',))
def api_store(request):
    try:
        data = _json_body(request)
        blockchain = data.get('blockchain', 'RBB')
        request.log_blockchain = blockchain
        hashes = bifrost_api.store(
            data.get('payload', ''),
            blockchain,
            pw=data.get('password') or None,
            multiple_tx=bool(data.get('multiple_tx', False)),
            redundancy=bool(data.get('redundancy', False)),
            owner=request.api_user.pk,
        )
        request.log_cost = _estimate_or_none(blockchain, data.get('payload', ''), bool(data.get('password')))
        request.log_hash = hashes[0] if hashes else ''
        return JsonResponse({
            'status': 'success', 'hashes': hashes, 'blockchain': blockchain,
            'estimated_cost': _cost_summary(request.log_cost),
        })
    except Exception as e:
        return _api_error(e)


@api_endpoint('retrieve', ('GET', 'POST'))
def api_retrieve(request):
    """GET ?hash=... ou POST {"hash": ...}. A senha nunca vai na URL: use o cabeçalho
    X-Bifrost-Password ou o campo "password" do corpo JSON (POST)."""
    try:
        if request.method == 'POST':
            data = _json_body(request)
            tx_hash = data.get('hash', '')
            pw = data.get('password') or request.headers.get('X-Bifrost-Password') or None
        else:
            tx_hash = request.GET.get('hash', '')
            pw = request.headers.get('X-Bifrost-Password') or None
        if not tx_hash:
            return JsonResponse({'status': 'error', 'message': 'O parâmetro hash é obrigatório.'}, status=400)
        return JsonResponse({'status': 'success', 'data': bifrost_api.retrieve(tx_hash, pw=pw, owner=request.api_user.pk)})
    except Exception as e:
        return _api_error(e)


@api_endpoint('migrate', ('POST',))
def api_migrate(request):
    try:
        data = _json_body(request)
        source_hash = data.get('source_hash', '')
        if not source_hash:
            raise ValueError('O campo source_hash é obrigatório.')
        target = data.get('target_blockchain', 'ETHEREUM')
        request.log_blockchain = target
        res = bifrost_api.migrate(
            source_hash, target, multiple_tx=bool(data.get('multiple_tx', False)), owner=request.api_user.pk,
        )
        request.log_cost = _estimate_or_none(target, res['payload_migrated'], False)
        request.log_hash = res['new_hashes'][0] if res.get('new_hashes') else ''
        res['estimated_cost'] = _cost_summary(request.log_cost)
        return JsonResponse({'status': 'success', 'data': res})
    except Exception as e:
        return _api_error(e)


@api_endpoint('transactions', ('GET',))
def api_transactions(request):
    txs = bifrost_db.get_all_transactions(owner=request.api_user.pk)
    return JsonResponse({'status': 'success', 'count': len(txs), 'transactions': txs})


def _cost_summary(cost):
    if not cost:
        return None
    return {
        'transactions': cost['fragments'], 'fee_native': cost['fee_native'],
        'symbol': cost['symbol'], 'fee_usd': cost['fee_usd'],
    }


# Estimativa de custo (antes do envio)

def _int_or_none(value, name):
    if value in (None, ''):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f'{name} deve ser um número inteiro.')
    if number <= 0 or number > 50_000_000:
        raise ValueError(f'{name} deve estar entre 1 e 50.000.000.')
    return number


def _run_estimate(data):
    """Interpreta os parâmetros (formulário ou JSON) e devolve (resultados, parâmetros usados)."""
    payload = data.get('payload') or None
    if payload is not None and not isinstance(payload, str):
        raise ValueError('O conteúdo deve ser um texto.')
    size = _int_or_none(data.get('size_bytes'), 'O tamanho em bytes')
    if payload is None and size is None:
        raise ValueError('Informe o conteúdo ou o tamanho em bytes.')
    encrypted = str(data.get('encrypted', '')).lower() in ('on', 'true', '1')
    multiple_tx = str(data.get('multiple_tx', '')).lower() in ('on', 'true', '1')
    overrides = {
        'gas_price_gwei': data.get('gas_price_gwei'),
        'fee_rate_sat_vb': data.get('fee_rate_sat_vb'),
        'stellar_base_fee_stroops': data.get('stellar_base_fee_stroops'),
        'usd_prices': {sym: data.get(f'usd_{sym.lower()}') for sym in ('ETH', 'BTC', 'XLM', 'EOS')},
    }
    params = bifrost_costs.resolve_params(overrides)
    results = bifrost_costs.estimate_all(
        payload=payload, size_bytes=size if payload is None else None,
        encrypted=encrypted, multiple_tx=multiple_tx, params=params,
    )
    return results, params


def _preview_response(chain, payload, encrypted, multiple_tx):
    chain_name = Blockchain.from_name(chain).name
    bifrost_api.identify_blockchain(chain_name)
    params = bifrost_costs.resolve_params()
    options = bifrost_costs.estimate_all(payload=payload, encrypted=encrypted, multiple_tx=multiple_tx, params=params)
    selected = next(o for o in options if o['blockchain'] == chain_name)
    usable = [o for o in options if o['feasible']]
    prices = params['usd_prices']
    return JsonResponse({
        'status': 'success',
        'selected': selected,
        'cheapest': usable[0] if usable else None,
        'options': [{k: o[k] for k in ('blockchain', 'name', 'symbol', 'fee_native', 'fee_usd', 'fragments', 'feasible')} for o in options],
        'assumptions': (
            f"Gas {params['gas_price_gwei']:g} gwei, Bitcoin {params['fee_rate_sat_vb']:g} sat/vB, "
            f"ETH US$ {prices['ETH']:g}, BTC US$ {prices['BTC']:g}, XLM US$ {prices['XLM']:g}."
        ),
    })


def _preview_json(request):
    if request.method != 'POST':
        raise ValueError('Use POST.')
    return _json_body(request)


@login_required
def preview_store_cost(request):
    """Custo estimado exibido no formulário de gravação, antes do envio."""
    try:
        data = _preview_json(request)
        payload = data.get('payload')
        if not isinstance(payload, str) or not payload.strip():
            raise ValueError('Informe o conteúdo para estimar o custo.')
        return _preview_response(data.get('blockchain', 'RBB'), payload.strip(), bool(data.get('encrypted')), bool(data.get('multiple_tx')))
    except Exception as e:
        return _api_error(e)


@login_required
def preview_migrate_cost(request):
    """Custo estimado da migração (usa o tamanho do dado que está na origem)."""
    try:
        data = _preview_json(request)
        source_hash = str(data.get('source_hash', '')).strip()
        if not source_hash:
            raise ValueError('Informe o hash de origem.')
        raw = bifrost_api.retrieve(source_hash, owner=request.user.pk)['payload']
        return _preview_response(data.get('target_blockchain', 'ETHEREUM'), raw, False, bool(data.get('multiple_tx')))
    except Exception as e:
        return _api_error(e)


@api_endpoint('estimate', ('POST',))
def api_estimate(request):
    """Estimativa de custo. Corpo JSON: payload ou size_bytes; opcionais: encrypted, multiple_tx,
    gas_price_gwei, fee_rate_sat_vb, stellar_base_fee_stroops, usd_eth, usd_btc, usd_xlm, usd_eos."""
    try:
        results, params = _run_estimate(_json_body(request))
        return JsonResponse({'status': 'success', 'params': params, 'estimates': results})
    except Exception as e:
        return _api_error(e)


# Contabilidade (administrador)

ORDERINGS = {
    'cost': ('-cost', '-txs', 'blockchain'),
    'txs': ('-txs', '-cost', 'blockchain'),
    'bytes': ('-volume', '-cost', 'blockchain'),
}
PERIODS = {'7': 7, '30': 30, '90': 90, 'all': None}


@staff_required
def admin_accounting_view(request):
    period = request.GET.get('period', '30')
    if period not in PERIODS:
        period = '30'
    order = request.GET.get('order', 'cost')
    if order not in ORDERINGS:
        order = 'cost'

    logs = RequestLog.objects.all()
    if PERIODS[period]:
        logs = logs.filter(created_at__gte=timezone.now() - datetime.timedelta(days=PERIODS[period]))
    spending = logs.filter(endpoint__in=('store', 'migrate'), status_code=200).exclude(blockchain='')

    chains = list(
        spending.values('blockchain').annotate(
            cost=Sum('cost_usd'), txs=Sum('tx_count'), volume=Sum('bytes_stored'),
            native=Sum('fee_native'), ops=Count('id'), users=Count('user', distinct=True),
        ).order_by(*ORDERINGS[order])
    )
    top_cost = max((c['cost'] or 0 for c in chains), default=0)
    for rank, row in enumerate(chains, start=1):
        row['rank'] = rank
        row['symbol'] = bifrost_costs.symbol_for(row['blockchain'])
        row['bar'] = round(100 * (row['cost'] or 0) / top_cost) if top_cost else 0

    users = list(
        spending.values('user__username').annotate(
            cost=Sum('cost_usd'), txs=Sum('tx_count'), ops=Count('id'),
        ).order_by('-cost', '-txs')[:10]
    )
    totals = spending.aggregate(cost=Sum('cost_usd'), txs=Sum('tx_count'), volume=Sum('bytes_stored'))
    ctx = get_context_base(request, 'admin_accounting')
    ctx.update({
        'chains': chains,
        'top_chain': chains[0] if chains else None,
        'top_users': users,
        'totals': totals,
        'requests_total': logs.count(),
        'requests_api': logs.filter(source='api').count(),
        'active_users': logs.values('user').distinct().count(),
        'period': period,
        'order': order,
        'periods': [('7', '7 dias'), ('30', '30 dias'), ('90', '90 dias'), ('all', 'Tudo')],
    })
    return render(request, 'admin_accounting.html', ctx)
