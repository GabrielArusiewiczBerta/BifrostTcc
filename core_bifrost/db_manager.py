import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from core_bifrost.blockchain import Blockchain
from core_bifrost.custom_errors import TransactionNotFoundError

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get('BIFROST_DB_PATH') or os.path.join(BASE_DIR, 'bifrost_db.sqlite3')


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def setup_database():
    with get_connection() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS blockchains (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL)')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                hash TEXT PRIMARY KEY,
                blockchain_id INTEGER NOT NULL,
                issued_at TIMESTAMP NOT NULL,
                salt TEXT,
                key TEXT,
                hash_next TEXT,
                payload_preview TEXT,
                FOREIGN KEY (blockchain_id) REFERENCES blockchains (id)
            )
        ''')
        # Armazenamento dos adaptadores em modo simulação (substitui a rede real).
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sim_storage (
                hash TEXT NOT NULL,
                adapter TEXT NOT NULL,
                data TEXT NOT NULL,
                PRIMARY KEY (hash, adapter)
            )
        ''')
        columns = [r['name'] for r in conn.execute('PRAGMA table_info(transactions)')]
        if 'owner' not in columns:
            conn.execute('ALTER TABLE transactions ADD COLUMN owner TEXT')
        for bc in Blockchain:
            conn.execute('INSERT OR IGNORE INTO blockchains (id, name) VALUES (?, ?)', (bc.value, bc.name))


def add_transaction(transaction_hash, chain, salt="", pw="", next_transaction="", payload_preview="", owner=None):
    now = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            'INSERT OR REPLACE INTO transactions (hash, blockchain_id, issued_at, salt, key, hash_next, payload_preview, owner) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (transaction_hash, chain.value, now, salt, pw, next_transaction, payload_preview,
             None if owner is None else str(owner))
        )


def find_transaction_information(transaction_hash):
    """Retorna dict com blockchain, salt, key (verificador), issued_at, hash_next e seq (ordem de inserção)."""
    with get_connection() as conn:
        row = conn.execute(
            'SELECT rowid AS seq, blockchain_id, salt, key, issued_at, hash_next, owner FROM transactions WHERE hash=?',
            (transaction_hash,)
        ).fetchone()
        if not row:
            raise TransactionNotFoundError(f"Transação com hash {transaction_hash} não foi encontrada no banco de dados.")
        return {
            'hash': transaction_hash,
            'blockchain': Blockchain(row['blockchain_id']),
            'salt': row['salt'] or '',
            'key': row['key'] or '',
            'issued_at': row['issued_at'],
            'hash_next': row['hash_next'] or '',
            'seq': row['seq'],
            'owner': row['owner'],
        }


def get_all_transactions(owner=None):
    """Lista do ledger (só do dono, se informado). Nunca inclui salt nem verificador de senha."""
    query = '''
        SELECT t.hash, b.name as blockchain_name, t.issued_at, t.salt, t.hash_next, t.payload_preview
        FROM transactions t
        JOIN blockchains b ON t.blockchain_id = b.id
    '''
    params = ()
    if owner is not None:
        query += ' WHERE t.owner = ?'
        params = (str(owner),)
    with get_connection() as conn:
        rows = conn.execute(query + ' ORDER BY t.issued_at DESC, t.rowid DESC', params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d['encrypted'] = bool(d.pop('salt'))
        result.append(d)
    return result


def get_transaction_count():
    with get_connection() as conn:
        return conn.execute('SELECT COUNT(*) as total FROM transactions').fetchone()['total']


def sim_put(tx_hash, adapter, data):
    with get_connection() as conn:
        conn.execute('INSERT OR REPLACE INTO sim_storage (hash, adapter, data) VALUES (?, ?, ?)', (tx_hash, adapter, data))


def sim_get(tx_hash, adapter):
    with get_connection() as conn:
        row = conn.execute('SELECT data FROM sim_storage WHERE hash=? AND adapter=?', (tx_hash, adapter)).fetchone()
    if not row:
        raise TransactionNotFoundError(f"Dados da transação {tx_hash} não encontrados no adaptador {adapter}.")
    return row['data']


setup_database()
