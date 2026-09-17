import sqlite3
import os
from datetime import datetime
from pathlib import Path
from core_bifrost.blockchain import Blockchain
from core_bifrost.custom_errors import TransactionNotFoundError

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.path.join(BASE_DIR, 'bifrost_db.sqlite3')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def setup_database():
    with get_connection() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS blockchains (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL)')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                blockchain_id INTEGER NOT NULL,
                address TEXT NOT NULL,
                key TEXT NOT NULL,
                user TEXT,
                password TEXT,
                FOREIGN KEY (blockchain_id) REFERENCES blockchains (id)
            )
        ''')
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
        
        # Seed blockchains
        for bc in Blockchain:
            conn.execute('INSERT OR IGNORE INTO blockchains (id, name) VALUES (?, ?)', (bc.value, bc.name))
            
        # Seed default credentials if empty
        cur = conn.execute('SELECT COUNT(*) as count FROM credentials')
        if cur.fetchone()['count'] == 0:
            default_creds = [
                (Blockchain.BITCOIN.value, 'bc1qtestnetaddress001', 'privkey_btc_demo', 'btc_user', 'btc_pass'),
                (Blockchain.ETHEREUM.value, '0x71C7656EC7ab88b098defB751B7401B5f6d8976F', '0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a6f363855', 'eth_user', 'eth_pass'),
                (Blockchain.STELLAR.value, 'GDQWYT7K2KXYZTESTNETSTELLARADDRESS001', 'SBTESTNETSTELLARPRIVKEY001', 'stellar_user', 'stellar_pass'),
                (Blockchain.EOS.value, 'EOS6MRyAjQq8ud7hVJJcf6t25NVPF8dUk3A71B255157', '5KQwrPbwdL6PhXujxW37FSSQZ1JiwsST4cqQzDeyXtP79zkvFD3', 'eos_user', 'eos_pass'),
                (Blockchain.POSTGRES.value, 'localhost:5432/bifrost', 'postgres_key', 'test', '123456'),
                (Blockchain.RBB.value, 'rbb_node_01', 'rbb_sec_key_2025', 'rbb_admin', 'rbb_pass_2025'),
            ]
            for c in default_creds:
                conn.execute('INSERT INTO credentials (blockchain_id, address, key, user, password) VALUES (?, ?, ?, ?, ?)', c)

def add_transaction(transaction_hash, chain, salt="", pw="", next_transaction="", payload_preview=""):
    now = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            'INSERT OR REPLACE INTO transactions (hash, blockchain_id, issued_at, salt, key, hash_next, payload_preview) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (transaction_hash, chain.value, now, salt, pw, next_transaction, payload_preview)
        )

def find_transaction_information(transaction_hash):
    with get_connection() as conn:
        cursor = conn.execute(
            'SELECT blockchain_id, salt, key, issued_at, hash_next, payload_preview FROM transactions WHERE hash=?',
            (transaction_hash,)
        )
        row = cursor.fetchone()
        if not row:
            raise TransactionNotFoundError(f"Transação com hash {transaction_hash} não foi encontrada no banco de dados.")
        return Blockchain(row['blockchain_id']), row['salt'], row['key'], row['issued_at'], row['hash_next']

def get_all_transactions():
    with get_connection() as conn:
        cursor = conn.execute('''
            SELECT t.hash, b.name as blockchain_name, t.issued_at, t.salt, t.key, t.hash_next, t.payload_preview
            FROM transactions t
            JOIN blockchains b ON t.blockchain_id = b.id
            ORDER BY t.issued_at DESC
        ''')
        return [dict(r) for r in cursor.fetchall()]

def get_transaction_count():
    with get_connection() as conn:
        cursor = conn.execute('SELECT COUNT(*) as total FROM transactions')
        return cursor.fetchone()['total']

# Initialize DB on module import
setup_database()
