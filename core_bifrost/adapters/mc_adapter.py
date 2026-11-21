from core_bifrost.adapters.base_adapter import BaseAdapter


class MCAdapter(BaseAdapter):
    NAME = "MultiChain"
    MAX_SIZE = 512
    HASH_PREFIX = "mc_"
