# append the root project path to the pythonpath so that blockchain.py can be accessed by every adapter
import sys
import os
import logging

sys.path.append(os.path.dirname(os.path.realpath(__file__)))

from custom_errors.custom_errors import TransactionSizeError, TransactionNotFoundError, \
    BlockchainNotFoundError
from adapters.btc_adapter import BTCAdapter
from adapters.mc_adapter import MCAdapter
from adapters.eth_adapter import EthAdapter
from adapters.postgres_adapter import PostgresAdapter
from adapters.stellar_adapter import StellarAdapter
from adapters.eos_adapter import EosAdapter
# from adapters.iota_adapter import IotaAdapter
#   NOTE: out-commented due to issues with iota package in this python 3.7.1 environment
# from adapters.hyperledger_adapter import HyperledgerAdapter

from blockchain import Blockchain
import db.database as database
import sys

Adapter = {
    Blockchain.BITCOIN: BTCAdapter,
    Blockchain.MULTICHAIN: MCAdapter,
    Blockchain.ETHEREUM: EthAdapter,
    Blockchain.POSTGRES: PostgresAdapter,
    Blockchain.STELLAR: StellarAdapter,
    Blockchain.EOS: EosAdapter,
    # Blockchain.IOTA: IotaAdapter,
    # Blockchain.HYPERLEDGER: HyperledgerAdapter

}


# Helper functions
def __identify_blockchain(blockchain):
    try:
        adapter = Adapter[blockchain]
        return adapter
    except:
        raise BlockchainNotFoundError


# API functions
def store(text, blockchain, pw=None, multiple_tx=False, redundancy=False):
    """Store a text in a specific Blockchain:
        Args:
            text:           Data to store.
            blockchain:     Blockchain to use, e.g. Ethereum.
            pw:             (optional) Password to encrypt data before storing it.
            multiple_tx:    (optional) dictates whether or not data may be split onto multiple transactions should
                            it exceed the BC-specific transaction data size limit.
            redundancy:     (optional) Redundancy parameter, if True stores a backup of the
                            data in a local postgres DB, using the postgres adapter.
        Returns:
            array:          The transaction hash array
    """
    try:
        adapter = __identify_blockchain(blockchain)
        transaction_hashes, salt, key = adapter.store_wrapper(text, pw, multiple_tx)
        salt = salt if salt is not None else ""
        key = key if key is not None else ""
        for i in range(len(transaction_hashes)):
            next_transaction = transaction_hashes[i + 1] if i < (len(transaction_hashes) - 1) else transaction_hashes[0]
            # if only one hash or in the last hash in the list, enter the first hash to close the loop of the linked
            # hashes
            database.add_transaction(transaction_hashes[i], blockchain, salt, key, next_transaction)
        if redundancy:
            transaction_hashes.append(
                store(text, Blockchain.POSTGRES, pw=pw, multiple_tx=multiple_tx, redundancy=False)[0])
        print(transaction_hashes)
        return transaction_hashes
    except TransactionSizeError as error:
        sys.tracebacklimit = 0
        logging.error(error)
        exit()
    except BlockchainNotFoundError as error:
        sys.tracebacklimit = 0
        logging.error(error)
        exit()
    except Exception as error:
        # treat any non-specified errors here
        sys.tracebacklimit = 1000  # default
        logging.exception(error, exc_info=True)
        exit()


def retrieve(transaction_hash, pw=None):
    """Get the text stored on the Blockchain:
        Args:
            transaction_hash:   Transaction hash
            pw:                 (optional) supply password to decrypt data before return
        Returns:
            string:             The data belonging to the transaction.
    """
    # handle potential encryption
    try:
        blockchain, salt, key, time_stamp, next_transaction = database.find_transaction_information(transaction_hash)
        adapter = __identify_blockchain(blockchain)
        salt = salt if salt != "" else None
        key = key if key != "" else None
        # handle data potentially split over multiple tx. can reconstruct entire data by
        # receiving any of the hashes of the involved TXs & respective time stamps
        transaction_hashes = [transaction_hash]
        time_stamps = [time_stamp]
        earliest_time_stamp = time_stamp
        while next_transaction != transaction_hashes[0]:
            transaction_hashes.append(next_transaction)
            _, _, _, next_stamp, next_transaction = database.find_transaction_information(next_transaction)
            time_stamps.append(next_stamp)
            if next_stamp < earliest_time_stamp:
                earliest_time_stamp = next_stamp
        # potential reorganization of retrieved hashes according to their time_stamps
        # https://stackoverflow.com/a/44901770 efficiency of rotation
        while time_stamps[0] != earliest_time_stamp:
            transaction_hashes.append(transaction_hashes.pop(0))
            time_stamps.append(time_stamps.pop(0))
        # call wrapper with needed parameters
        if pw:
            text = adapter.retrieve_wrapper(transaction_hashes, pw, salt, key)
        else:
            text = adapter.retrieve_wrapper(transaction_hashes)
        print(text)
        return text
    except TransactionNotFoundError as error:
        sys.tracebacklimit = 0
        logging.error(error)
        exit()
    except Exception as error:
        # treat any non-specified errors here
        sys.tracebacklimit = 1000  # default
        logging.exception(error, exc_info=True)
        exit()


def migrate(transaction_hash, blockchain, multiple_tx=False):
    """Copy a value from a transaction to another Blockchain:
        Args:
            transaction_hash:       Transaction hash
            blockchain:             blockchain to use, e.g., Ethereum
            multiple_tx:            (optional) dictates whether or not data may be split onto multiple transactions
                                    should it exceed the BC-specific transaction data size limit.
        Returns:
            array:                 The transaction hashes from the new transaction.
    """
    value = retrieve(transaction_hash)
    new_hashes = store(value, blockchain, multiple_tx=multiple_tx)
    # handle potential encryption -> store salt & key in DB for the new transaction as well
    _, salt, key, _, _ = database.find_transaction_information(transaction_hash)
    # no error handling here, not even for find_transaction_information, as that
    # is already being called in the retrieve function which occurs previously and where
    # it is does have error handling
    for i in range(len(new_hashes)):
        database.add_encryption_info(new_hashes[i], salt, key)
    return new_hashes

#

#

# -----------------------------------------------

# print(store("timoishere", Blockchain.STELLAR))

# print(
#     retrieve(
#         "e229c47f66d3ed3b9076e86a37862738a2e5770009654e8a3cc75458924851da"
#     ))
# print(migrate("f12cc0275e47d8040c04d0ea0d26bf8117f25e0628697da338f73e1eb3d39cad;25316099",
#         Blockchain.STELLAR))
