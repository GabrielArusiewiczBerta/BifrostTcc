import hashlib
import uuid
from core_bifrost.adapters.base_adapter import BaseAdapter

class StellarAdapter(BaseAdapter):
    NAME = "Stellar"
    MAX_SIZE = 28  # Stellar Memo_Text payload limit

    _tx_store = {}

    @classmethod
    def store_chunk(cls, chunk: str) -> str:
        tx_hash = hashlib.sha256(f"stellar_tx:{uuid.uuid4()}:{chunk}".encode('utf-8')).hexdigest()
        cls._tx_store[tx_hash] = chunk
        return tx_hash

    @classmethod
    def retrieve_chunk(cls, tx_hash: str) -> str:
        return cls._tx_store.get(tx_hash, f"Stellar MEMO data for tx {tx_hash[:16]}")
