import os
import sys

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bifrost_project.settings')

import django
django.setup()

import core_bifrost.api as bifrost_api
import core_bifrost.db_manager as bifrost_db
from core_bifrost.blockchain import Blockchain

print("=== VERIFICANDO AMBIENTE E CORE BIFROST ===")

# Test 1: Store data on RBB (Rede Blockchain Brasil)
h_rbb = bifrost_api.store("Informacao de teste para Rede Blockchain Brasil - Edital FAPERGS 2024", Blockchain.RBB, pw="senha123", redundancy=True)
print(f"[STORE RBB] Hashes gerados: {h_rbb}")

# Test 2: Store data on Stellar
h_stellar = bifrost_api.store("Stellar Memo Test Data payload", Blockchain.STELLAR, multiple_tx=True)
print(f"[STORE STELLAR] Hashes gerados: {h_stellar}")

# Test 3: Retrieve data
res_retrieved = bifrost_api.retrieve(h_rbb[0], pw="senha123")
print(f"[RETRIEVE RBB] Blockchain: {res_retrieved['blockchain']} | Payload: {res_retrieved['payload']}")

# Test 4: Migrate data to Ethereum
res_migrated = bifrost_api.migrate(h_rbb[0], Blockchain.ETHEREUM)
print(f"[MIGRATE RBB->ETH] Origem: {res_migrated['source_blockchain']} -> Destino: {res_migrated['target_blockchain']} | Novos Hashes: {res_migrated['new_hashes']}")

# Test 5: Check database transactions count
txs = bifrost_db.get_all_transactions()
print(f"[DATABASE CHECK] Total de transações gravadas no SQLite: {len(txs)}")

print("=== TUDO VERIFICADO COM SUCESSO! ===")
