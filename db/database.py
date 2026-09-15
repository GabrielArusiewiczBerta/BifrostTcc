from sqlite3 import connect, Row
from datetime import datetime
from blockchain import Blockchain
from db.config import DATABASE_PATH, CREDENTIALS, TRANSACTIONS
from custom_errors.custom_errors import TransactionNotFoundError


connection = connect(DATABASE_PATH)
# Rows wrapped with the Row class can be accessed both by index (like tuples)
# and case-insensitively by name
connection.row_factory = Row


def with_connection(func):
    def wrapper(*args, **kwargs):
        with connection:
            return func(*args, **kwargs)
    return wrapper


def setup():
    drop_tables_if_exist()
    create_tables()
    seed_blockchains()
    seed_credentials()
    seed_transactions()


@with_connection
def drop_tables_if_exist():
    connection.execute('DROP TABLE IF EXISTS blockchains')
    connection.execute('DROP TABLE IF EXISTS credentials')
    connection.execute('DROP TABLE IF EXISTS transactions')


@with_connection
def create_tables():
    connection.execute(
        '''
        CREATE TABLE blockchains
        (id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        UNIQUE (name COLLATE NOCASE))
        '''
    )
    connection.execute(
        '''
        CREATE TABLE credentials 
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
        blockchain_id INTEGER NOT NULL, 
        address TEXT NOT NULL, 
        key TEXT NOT NULL, 
        user TEXT, 
        password TEXT,
        FOREIGN KEY (blockchain_id) REFERENCES blockchains (id))
        '''
    )
    connection.execute(
        '''
        CREATE TABLE transactions 
        (hash TEXT PRIMARY KEY, 
        blockchain_id INTEGER NOT NULL, 
        issued_at TIMESTAMP NOT NULL,
        salt TEXT,
        key TEXT,
        hash_next TEXT,
        FOREIGN KEY (blockchain_id) REFERENCES blockchains (id))
        '''
    )


@with_connection
def seed_blockchains():
    for bc in Blockchain:
        connection.execute(
            '''
        INSERT INTO blockchains
        VALUES (?, ?)
        ''',
            (bc.value, bc.name)
        )


@with_connection
def seed_credentials():
    for creds in CREDENTIALS:
        connection.execute(
            '''
            INSERT INTO credentials (blockchain_id, address, key, user, password) 
            VALUES (?, ?, ?, ?, ?)
            ''',
            (creds["id"], creds["address"], creds["key"],
             creds["user"], creds["password"])
        )


@with_connection
def seed_transactions():
    for tx in TRANSACTIONS:
        now = datetime.now()
        salt = ""
        key = ""
        next_transaction = ""
        connection.execute(
            'INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?)',
            (tx["transaction_hash"], tx["blockchain"], now, salt, key, next_transaction)
        )


@with_connection
def add_transaction(transaction_hash, chain, salt, pw, next_transaction):
    # next_transaction indicates that data was split over multiple transactions
    # and dictates the order in which the transactions belong together
    now = datetime.now()
    connection.execute(
        'INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?)',
        (transaction_hash, chain.value, now, salt, pw, next_transaction)
    )


@with_connection
def find_credentials(blockchain):
    blockchain_id = blockchain.value
    cursor = connection.execute(
        '''
        SELECT address, key, user, password 
        FROM credentials 
        WHERE blockchain_id=?
        ''',
        (blockchain_id,)
    )
    row = cursor.fetchone()
    return row


@with_connection
def find_latest_transaction(blockchain):
    blockchain_id = blockchain.value
    cursor = connection.execute(
        '''
        SELECT hash 
        FROM transactions 
        WHERE blockchain_id=? 
        ORDER BY issued_at DESC 
        LIMIT 1
        ''',
        (blockchain_id,)
    )
    row = cursor.fetchone()
    return row['hash']


@with_connection
def find_transaction_information(transaction_hash):
    # retrieve necessary information about given transaction
    try:
        cursor = connection.execute(
            'SELECT blockchain_id, salt, key, issued_at, hash_next FROM transactions WHERE hash=?',
            (transaction_hash,)
        )
        row = cursor.fetchone()
        blockchain_id = row['blockchain_id']
        return Blockchain(blockchain_id), row['salt'], row['key'], row['issued_at'], row['hash_next']
    except:
        raise TransactionNotFoundError

@with_connection
def add_encryption_info(transaction_hash, salt, key):
    # enriches existing transaction entry with salt & key data
    connection.execute(
        '''
        UPDATE transactions
        SET salt=?, key=?
        WHERE hash=?
        ''',
        (salt, key, transaction_hash)
    )
    connection.commit()

# @with_connection
# def update_credentials(blockchain, address, key, user='', password=''):
#     blockchain_id = blockchain.value
#     connection.execute(
#         '''
#         UPDATE credentials
#         SET address=?, key=?, user=?, password=?
#         WHERE id=?
#         ''',
#         (address, key, user, password, blockchain_id)
#     )
