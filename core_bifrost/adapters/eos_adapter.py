from core_bifrost.adapters.base_adapter import BaseAdapter


class EosAdapter(BaseAdapter):
    NAME = "EOS"
    MAX_SIZE = 256
    HASH_PREFIX = ""
