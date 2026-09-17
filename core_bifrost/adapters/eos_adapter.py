import hashlib
import uuid
from core_bifrost.adapters.base_adapter import BaseAdapter

class EosAdapter(BaseAdapter):
    NAME = "EOS"
    MAX_SIZE = 256

    _tx_store = {}

    @classmethod
    def store_chunk(cls, chunk: str) -> str:
        tx_hash = hashlib.sha256(f"eos_tx:{uuid.uuid4()}:{chunk}".encode('utf-8')).hexdigest()
        cls._tx_store[tx_hash] = chunk
        return tx_hash

    @classmethod
    def retrieve_chunk(cls, tx_hash: str) -> str:
        return cls._tx_store.get(tx_hash, f"EOS Memo payload for tx {tx_hash[:16]}")
