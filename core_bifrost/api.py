import logging
from core_bifrost.blockchain import Blockchain
from core_bifrost.custom_errors import BlockchainNotFoundError, TransactionNotFoundError
import core_bifrost.db_manager as db

from core_bifrost.adapters.btc_adapter import BTCAdapter
from core_bifrost.adapters.eth_adapter import EthAdapter
from core_bifrost.adapters.stellar_adapter import StellarAdapter
from core_bifrost.adapters.eos_adapter import EosAdapter
from core_bifrost.adapters.postgres_adapter import PostgresAdapter
from core_bifrost.adapters.rbb_adapter import RBBAdapter
from core_bifrost.adapters.mc_adapter import MCAdapter

AdapterRegistry = {
    Blockchain.BITCOIN: BTCAdapter,
    Blockchain.ETHEREUM: EthAdapter,
    Blockchain.STELLAR: StellarAdapter,
    Blockchain.EOS: EosAdapter,
    Blockchain.POSTGRES: PostgresAdapter,
    Blockchain.RBB: RBBAdapter,
    Blockchain.MULTICHAIN: MCAdapter,
    Blockchain.HYPERLEDGER: RBBAdapter,
    Blockchain.IOTA: StellarAdapter,
}

def identify_blockchain(blockchain: Blockchain):
    if isinstance(blockchain, str):
        blockchain = Blockchain.from_name(blockchain)
    if blockchain in AdapterRegistry:
        return AdapterRegistry[blockchain]
    raise BlockchainNotFoundError(f"Adaptador não encontrado para a blockchain: {blockchain}")

def store(text: str, blockchain, pw: str = None, multiple_tx: bool = False, redundancy: bool = False):
    """
    Store payload in selected blockchain using Bifröst adapter.
    """
    if isinstance(blockchain, str):
        blockchain = Blockchain.from_name(blockchain)
        
    adapter = identify_blockchain(blockchain)
    transaction_hashes, salt, key = adapter.store_wrapper(text, pw, multiple_tx)
    
    salt = salt if salt else ""
    key = key if key else ""
    
    payload_preview = text[:40] + ("..." if len(text) > 40 else "")
    
    for i in range(len(transaction_hashes)):
        tx_h = transaction_hashes[i]
        next_h = transaction_hashes[i + 1] if i < (len(transaction_hashes) - 1) else transaction_hashes[0]
        db.add_transaction(tx_h, blockchain, salt, key, next_h, payload_preview)
        
    if redundancy and blockchain != Blockchain.POSTGRES:
        pg_hashes = store(text, Blockchain.POSTGRES, pw=pw, multiple_tx=multiple_tx, redundancy=False)
        transaction_hashes.extend(pg_hashes)
        
    return transaction_hashes

def retrieve(transaction_hash: str, pw: str = None):
    """
    Retrieve stored payload by transaction hash, resolving multi-tx chaining and encryption.
    """
    blockchain, salt, key, issued_at, next_transaction = db.find_transaction_information(transaction_hash)
    adapter = identify_blockchain(blockchain)
    
    salt_val = salt if salt != "" else None
    key_val = key if key != "" else None
    
    transaction_hashes = [transaction_hash]
    
    # Resolve linked transaction sequence if data was split across multiple transactions
    while next_transaction and next_transaction != transaction_hashes[0] and next_transaction not in transaction_hashes:
        transaction_hashes.append(next_transaction)
        _, _, _, _, next_transaction = db.find_transaction_information(next_transaction)
        
    data = adapter.retrieve_wrapper(transaction_hashes, pw=pw, salt=salt_val, key=key_val)
    return {
        'blockchain': blockchain.name,
        'transaction_hash': transaction_hash,
        'linked_hashes': transaction_hashes,
        'payload': data,
        'encrypted': bool(salt_val),
        'issued_at': issued_at
    }

def migrate(transaction_hash: str, target_blockchain, multiple_tx: bool = False):
    """
    Migrate data from an existing transaction hash to a new target blockchain.
    """
    if isinstance(target_blockchain, str):
        target_blockchain = Blockchain.from_name(target_blockchain)
        
    retrieved_info = retrieve(transaction_hash)
    payload = retrieved_info['payload']
    
    new_hashes = store(payload, target_blockchain, multiple_tx=multiple_tx)
    return {
        'source_hash': transaction_hash,
        'source_blockchain': retrieved_info['blockchain'],
        'target_blockchain': target_blockchain.name,
        'new_hashes': new_hashes,
        'payload_migrated': payload
    }
