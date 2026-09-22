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
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

import core_bifrost.api as bifrost_api
import core_bifrost.costs as bifrost_costs
import core_bifrost.db_manager as bifrost_db
from core_bifrost.blockchain import Blockchain
from core_bifrost.custom_errors import (
    TransactionSizeError, TransactionNotFoundError, BlockchainNotFoundError, DecryptionError,
)

from .models import ApiKey, RequestLog

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


def _log_request(user, source, endpoint, method, status_code, blockchain='', cost=None):
    cost = cost or {}
    RequestLog.objects.create(
        user=user, source=source, endpoint=endpoint, method=method,
        status_code=status_code, blockchain=str(blockchain or '')[:20],
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


def get_context_base(request, active_tab='dashboard'):
    txs = bifrost_db.get_all_transactions(owner=request.user.pk)
    return {
        'active_tab': active_tab,
        'blockchains': BLOCKCHAIN_METADATA,
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
        messages.success(request, 'Conta criada. Bem-vindo ao Bifröst!')
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
        defaults={'key_hash': hashlib.sha256(raw_key.encode()).hexdigest(), 'prefix': raw_key[:12], 'last_used_at': None},
    )
    ctx = _account_context(request)
    ctx['new_api_key'] = raw_key
    return render(request, 'account.html', ctx)


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
        _log_request(request.user, 'web', 'store', 'POST', status, blockchain_code, cost)
        ctx.update(get_context_base(request, 'store'))

    return render(request, 'store.html', ctx)


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
        _log_request(request.user, 'web', 'migrate', 'POST', status, target_blockchain, cost)
        ctx.update(get_context_base(request, 'migrate'))

    return render(request, 'migrate.html', ctx)


@login_required
def explorer_view(request):
    return render(request, 'explorer.html', get_context_base(request, 'explorer'))


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
            request.api_user = api_key.user
            ApiKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())

            if request.method not in methods:
                response = JsonResponse({'error': f"Método não permitido. Use {' ou '.join(methods)}."}, status=405)
            else:
                response = view(request)
            _log_request(request.api_user, 'api', name, request.method, response.status_code,
                         getattr(request, 'log_blockchain', ''), getattr(request, 'log_cost', None))
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
