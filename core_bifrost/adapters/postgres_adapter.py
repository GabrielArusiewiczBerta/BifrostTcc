from core_bifrost.adapters.base_adapter import BaseAdapter


class PostgresAdapter(BaseAdapter):
    NAME = "PostgreSQL"
    MAX_SIZE = 4096
    HASH_PREFIX = "pg_"
