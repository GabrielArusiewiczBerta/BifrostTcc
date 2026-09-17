import hashlib
import uuid
from core_bifrost.adapters.base_adapter import BaseAdapter

class MCAdapter(BaseAdapter):
    NAME = "MultiChain"
    MAX_SIZE = 512

    _tx_store = {}

    @classmethod
    def store_chunk(cls, chunk: str) -> str:
        tx_hash = "mc_" + hashlib.sha256(f"mc_tx:{uuid.uuid4()}:{chunk}".encode('utf-8')).hexdigest()
        cls._tx_store[tx_hash] = chunk
        return tx_hash

    @classmethod
    def retrieve_chunk(cls, tx_hash: str) -> str:
        return cls._tx_store.get(tx_hash, f"MultiChain stream item for {tx_hash[:16]}")
