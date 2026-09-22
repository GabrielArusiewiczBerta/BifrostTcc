from core_bifrost.adapters.base_adapter import BaseAdapter


class EthAdapter(BaseAdapter):
    NAME = "Ethereum"
    MAX_SIZE = 1024
    HASH_PREFIX = "0x"
