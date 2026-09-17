import hashlib
import uuid
from core_bifrost.adapters.base_adapter import BaseAdapter

class EthAdapter(BaseAdapter):
    NAME = "Ethereum"
    MAX_SIZE = 1024  # Ethereum tx payload limit for demo/testnet

    _tx_store = {}

    @classmethod
    def store_chunk(cls, chunk: str) -> str:
        tx_hash = "0x" + hashlib.sha256(f"eth_tx:{uuid.uuid4()}:{chunk}".encode('utf-8')).hexdigest()
        cls._tx_store[tx_hash] = chunk
        return tx_hash

    @classmethod
    def retrieve_chunk(cls, tx_hash: str) -> str:
        return cls._tx_store.get(tx_hash, f"CallData payload for ETH tx {tx_hash[:16]}")
