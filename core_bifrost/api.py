import core_bifrost.db_manager as db
from core_bifrost.blockchain import Blockchain
from core_bifrost.custom_errors import BlockchainNotFoundError, TransactionNotFoundError

from core_bifrost.adapters.btc_adapter import BTCAdapter
from core_bifrost.adapters.eth_adapter import EthAdapter
from core_bifrost.adapters.stellar_adapter import StellarAdapter
from core_bifrost.adapters.eos_adapter import EosAdapter
from core_bifrost.adapters.postgres_adapter import PostgresAdapter
from core_bifrost.adapters.rbb_adapter import RBBAdapter
from core_bifrost.adapters.mc_adapter import MCAdapter

# HYPERLEDGER e IOTA existem no enum, mas ainda não têm adaptador.
AdapterRegistry = {
    Blockchain.BITCOIN: BTCAdapter,
    Blockchain.ETHEREUM: EthAdapter,
    Blockchain.STELLAR: StellarAdapter,
    Blockchain.EOS: EosAdapter,
    Blockchain.POSTGRES: PostgresAdapter,
    Blockchain.RBB: RBBAdapter,
    Blockchain.MULTICHAIN: MCAdapter,
}

ENCRYPTED_PREVIEW = "[criptografado]"


def identify_blockchain(blockchain):
    if isinstance(blockchain, str):
        blockchain = Blockchain.from_name(blockchain)
    if blockchain in AdapterRegistry:
        return AdapterRegistry[blockchain]
    raise BlockchainNotFoundError(f"Adaptador não encontrado para a blockchain: {blockchain.name}")


def _preview(text: str, encrypted: bool) -> str:
    if encrypted:
        return ENCRYPTED_PREVIEW
    return text[:40] + ("..." if len(text) > 40 else "")


def _record(hashes, blockchain, salt, key, preview, owner=None):
    """Grava no ledger, encadeando cada hash ao próximo (o último aponta para o primeiro)."""
    for i, tx_h in enumerate(hashes):
        next_h = hashes[i + 1] if i < len(hashes) - 1 else hashes[0]
        db.add_transaction(tx_h, blockchain, salt, key, next_h, preview, owner)


def _load_chain(transaction_hash: str, owner=None):
    """Percorre o anel de hashes ligados e devolve os registros do mais antigo ao mais novo.
    Se `owner` for informado, só enxerga transações desse dono."""
    first = db.find_transaction_information(transaction_hash)
    if owner is not None and first['owner'] != str(owner):
        raise TransactionNotFoundError(f"Transação com hash {transaction_hash} não foi encontrada no banco de dados.")
    records = [first]
    seen = {transaction_hash}
    nxt = first['hash_next']
    while nxt and nxt not in seen:
        rec = db.find_transaction_information(nxt)
        records.append(rec)
        seen.add(nxt)
        nxt = rec['hash_next']
    records.sort(key=lambda r: (r['issued_at'], r['seq']))
    return records


def store(text: str, blockchain, pw: str = None, multiple_tx: bool = False, redundancy: bool = False, owner=None):
    """Armazena o payload na blockchain escolhida, com fragmentação e criptografia opcionais."""
    if not text:
        raise ValueError("O conteúdo a armazenar não pode ser vazio.")
    if isinstance(blockchain, str):
        blockchain = Blockchain.from_name(blockchain)

    adapter = identify_blockchain(blockchain)
    hashes, salt, key = adapter.store_wrapper(text, pw, multiple_tx)
    _record(hashes, blockchain, salt, key, _preview(text, bool(pw)), owner)

    if redundancy and blockchain != Blockchain.POSTGRES:
        hashes = hashes + store(text, Blockchain.POSTGRES, pw=pw, multiple_tx=multiple_tx, redundancy=False, owner=owner)

    return hashes


def retrieve(transaction_hash: str, pw: str = None, owner=None):
    """Recupera o payload a partir de qualquer hash da cadeia, na ordem original dos fragmentos."""
    chain = _load_chain(transaction_hash, owner)
    first = chain[0]
    adapter = identify_blockchain(first['blockchain'])
    salt, key = first['salt'] or None, first['key'] or None

    hashes = [r['hash'] for r in chain]
    data = adapter.retrieve_wrapper(hashes, pw=pw, salt=salt, key=key)
    return {
        'blockchain': first['blockchain'].name,
        'transaction_hash': transaction_hash,
        'linked_hashes': hashes,
        'payload': data,
        'encrypted': bool(salt),
        'decrypted': bool(salt and pw),
        'issued_at': first['issued_at'],
    }


def migrate(transaction_hash: str, target_blockchain, multiple_tx: bool = False, owner=None):
    """Copia o dado (mantendo-o cifrado, se for o caso) para outra blockchain, preservando salt e verificador."""
    if isinstance(target_blockchain, str):
        target_blockchain = Blockchain.from_name(target_blockchain)

    chain = _load_chain(transaction_hash, owner)
    first = chain[0]
    source_adapter = identify_blockchain(first['blockchain'])
    target_adapter = identify_blockchain(target_blockchain)

    salt, key = first['salt'], first['key']
    payload = source_adapter.retrieve_wrapper([r['hash'] for r in chain])

    new_hashes, _, _ = target_adapter.store_wrapper(payload, None, multiple_tx)
    _record(new_hashes, target_blockchain, salt, key, _preview(payload, bool(salt)), owner)

    return {
        'source_hash': transaction_hash,
        'source_blockchain': first['blockchain'].name,
        'target_blockchain': target_blockchain.name,
        'new_hashes': new_hashes,
        'encrypted': bool(salt),
        'payload_migrated': payload,
    }
