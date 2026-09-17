import json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt

import core_bifrost.api as bifrost_api
import core_bifrost.db_manager as bifrost_db
from core_bifrost.blockchain import Blockchain
from core_bifrost.custom_errors import TransactionSizeError, TransactionNotFoundError, BlockchainNotFoundError

BLOCKCHAIN_METADATA = [
    {'code': 'RBB', 'name': 'Rede Blockchain Brasil', 'icon': 'fa-shield-halved', 'badge': 'emerald', 'type': 'Permissionada (Hyperledger Besu)', 'max_size': '512 bytes', 'status': 'Online'},
    {'code': 'BITCOIN', 'name': 'Bitcoin Testnet', 'icon': 'fa-bitcoin', 'badge': 'amber', 'type': 'Pública (OP_RETURN)', 'max_size': '80 bytes', 'status': 'Online'},
    {'code': 'ETHEREUM', 'name': 'Ethereum Sepolia', 'icon': 'fa-ethereum', 'badge': 'indigo', 'type': 'Pública (Calldata / Smart Contract)', 'max_size': '1024 bytes', 'status': 'Online'},
    {'code': 'STELLAR', 'name': 'Stellar Testnet', 'icon': 'fa-rocket', 'badge': 'cyan', 'type': 'Pública (Memo_Text)', 'max_size': '28 bytes', 'status': 'Online'},
    {'code': 'EOS', 'name': 'EOS Jungle', 'icon': 'fa-bolt', 'badge': 'purple', 'type': 'Pública (Action Memo)', 'max_size': '256 bytes', 'status': 'Online'},
    {'code': 'POSTGRES', 'name': 'PostgreSQL Mirror', 'icon': 'fa-database', 'badge': 'blue', 'type': 'Banco Relacional de Redundância', 'max_size': '4096 bytes', 'status': 'Online'},
    {'code': 'MULTICHAIN', 'name': 'MultiChain Private', 'icon': 'fa-link', 'badge': 'rose', 'type': 'Privada (Streams)', 'max_size': '512 bytes', 'status': 'Online'},
]

def get_context_base(active_tab='dashboard'):
    txs = bifrost_db.get_all_transactions()
    return {
        'active_tab': active_tab,
        'blockchains': BLOCKCHAIN_METADATA,
        'total_transactions': len(txs),
        'active_nodes_count': len(BLOCKCHAIN_METADATA),
        'recent_transactions': txs[:5],
        'all_transactions': txs,
    }

def dashboard_view(request):
    ctx = get_context_base('dashboard')
    return render(request, 'dashboard.html', ctx)

def store_view(request):
    ctx = get_context_base('store')
    
    if request.method == 'POST':
        payload = request.POST.get('payload', '').strip()
        blockchain_code = request.POST.get('blockchain', 'RBB')
        password = request.POST.get('password', '').strip() or None
        multiple_tx = request.POST.get('multiple_tx') == 'on'
        redundancy = request.POST.get('redundancy') == 'on'
        
        if not payload:
            messages.error(request, 'Por favor, insira o conteúdo/dado que deseja armazenar.')
            return render(request, 'store.html', ctx)
            
        try:
            hashes = bifrost_api.store(
                text=payload,
                blockchain=blockchain_code,
                pw=password,
                multiple_tx=multiple_tx,
                redundancy=redundancy
            )
            ctx['success_result'] = {
                'hashes': hashes,
                'blockchain': blockchain_code,
                'payload_preview': payload[:80],
                'encrypted': bool(password),
                'count': len(hashes)
            }
            messages.success(request, f'Sucesso! {len(hashes)} transação(ões) gravada(s) na blockchain {blockchain_code}.')
        except TransactionSizeError as err:
            messages.error(request, f'Erro de Tamanho: {str(err)}')
        except Exception as err:
            messages.error(request, f'Erro durante o armazenamento: {str(err)}')
            
    return render(request, 'store.html', ctx)

def retrieve_view(request):
    ctx = get_context_base('retrieve')
    tx_hash = request.GET.get('hash', '') or request.POST.get('hash', '')
    password = request.POST.get('password', '') or None
    
    ctx['input_hash'] = tx_hash
    
    if tx_hash:
        try:
            result = bifrost_api.retrieve(tx_hash, pw=password)
            ctx['retrieved_result'] = result
            messages.success(request, f'Transação localizada e processada com sucesso!')
        except TransactionNotFoundError as err:
            messages.error(request, f'Transação não encontrada: {str(err)}')
        except Exception as err:
            messages.error(request, f'Falha ao recuperar dados: {str(err)}')
            
    return render(request, 'retrieve.html', ctx)

def migrate_view(request):
    ctx = get_context_base('migrate')
    
    if request.method == 'POST':
        source_hash = request.POST.get('source_hash', '').strip()
        target_blockchain = request.POST.get('target_blockchain', 'ETHEREUM')
        multiple_tx = request.POST.get('multiple_tx') == 'on'
        
        if not source_hash:
            messages.error(request, 'Forneça o Hash de transação de origem.')
            return render(request, 'migrate.html', ctx)
            
        try:
            result = bifrost_api.migrate(source_hash, target_blockchain, multiple_tx=multiple_tx)
            ctx['migration_result'] = result
            messages.success(request, f'Dados migrados com sucesso para a blockchain {target_blockchain}!')
        except Exception as err:
            messages.error(request, f'Erro na migração: {str(err)}')
            
    return render(request, 'migrate.html', ctx)

def explorer_view(request):
    ctx = get_context_base('explorer')
    return render(request, 'explorer.html', ctx)

# REST API Handlers

@csrf_exempt
def api_store(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido. Use POST.'}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8'))
        payload = data.get('payload', '')
        blockchain = data.get('blockchain', 'RBB')
        pw = data.get('password', None)
        multiple_tx = data.get('multiple_tx', False)
        redundancy = data.get('redundancy', False)
        
        hashes = bifrost_api.store(payload, blockchain, pw=pw, multiple_tx=multiple_tx, redundancy=redundancy)
        return JsonResponse({'status': 'success', 'hashes': hashes, 'blockchain': blockchain})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@csrf_exempt
def api_retrieve(request):
    tx_hash = request.GET.get('hash', '')
    pw = request.GET.get('password', None)
    if not tx_hash:
        return JsonResponse({'error': 'Parâmetro ?hash= é obrigatório.'}, status=400)
    try:
        res = bifrost_api.retrieve(tx_hash, pw=pw)
        return JsonResponse({'status': 'success', 'data': res})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=404)

@csrf_exempt
def api_migrate(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido. Use POST.'}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8'))
        source_hash = data.get('source_hash', '')
        target_blockchain = data.get('target_blockchain', 'ETHEREUM')
        multiple_tx = data.get('multiple_tx', False)
        
        res = bifrost_api.migrate(source_hash, target_blockchain, multiple_tx=multiple_tx)
        return JsonResponse({'status': 'success', 'data': res})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@csrf_exempt
def api_transactions(request):
    txs = bifrost_db.get_all_transactions()
    return JsonResponse({'status': 'success', 'count': len(txs), 'transactions': txs})
