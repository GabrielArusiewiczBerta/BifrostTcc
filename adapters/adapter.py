from abc import ABC, abstractmethod
from db.config import CONFIRMATION_WAITING_TIMES, ENCODING, TRANSACTION_SIZE_LIMITS
import time
import os
import base64
import math
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from custom_errors.custom_errors import TransactionSizeError, TransactionNotFoundError


class Adapter(ABC):

    ####################
    # ---PROPERTIES--- #
    ####################
    @property
    @abstractmethod
    def chain(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def credentials(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def address(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def key(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def client(self):
        raise NotImplementedError

    ####################
    # ---ENCRYPTION--- #
    ####################
    @staticmethod
    def encrypt(text, pw):
        # generate salt, build kdf, generate keys
        # key_1 used for password verification
        # key_2 used for encryption/decryption
        #
        # NOTE: encode & decode since API receives and stores data in string format but the
        #   cryptography library works in byte-format
        pw = pw.encode()
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(),
                         length=32,
                         salt=salt,
                         iterations=100000,
                         backend=default_backend())
        kdf_2 = PBKDF2HMAC(algorithm=hashes.SHA256(),
                           length=32, salt=salt,
                           iterations=100000,
                           backend=default_backend())
        # NOTE: kdf function only usable once, hence duplicate to generate key_2 (no deep-copy support)
        key_1 = base64.urlsafe_b64encode(kdf.derive(pw))
        key_2 = base64.urlsafe_b64encode(kdf_2.derive(pw + key_1))
        f = Fernet(key_2)
        text_encrypted = f.encrypt(text.encode())
        # return data, text_encrypted as string, salt and key_1 in byte-format
        return text_encrypted.decode(ENCODING), salt, key_1

    @staticmethod
    def decrypt(text, pw, salt, key_1):
        # given received pw and stored salt & key, build key_2 to decrypt
        pw = pw.encode()
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(),
                         length=32,
                         salt=salt,
                         iterations=100000,
                         backend=default_backend())
        key_2 = base64.urlsafe_b64encode(kdf.derive(pw + key_1))
        f = Fernet(key_2)
        text_decrypted = f.decrypt(text.encode())
        return text_decrypted.decode(ENCODING)

    @staticmethod
    def verify_password(pw, salt, key):
        # given a password input, verify whether it can reproduce the originally derived key
        if salt is None or key is None:
            return False
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(),
                         length=32,
                         salt=salt,
                         iterations=100000,
                         backend=default_backend())
        key_attempt = base64.urlsafe_b64encode(kdf.derive(pw.encode()))
        return key == key_attempt

    #######################
    # ---SIZE CHECKING--- #
    #######################
    @classmethod
    def get_text_size(cls, text):
        # source: https://stackoverflow.com/a/30686735
        return len(text.encode('utf-8'))

    @classmethod
    def determine_nr_of_tx(cls, text, limit):
        # determines the number of tx needed, given text's byte size
        size = cls.get_text_size(text)
        return math.ceil(size/limit)

    ###############
    # ---STORE--- #
    ###############
    @classmethod
    def store_wrapper(cls, text, pw=None, multiple_tx=False):
        # wrapper function for original store method
        # perform encryption if pw provided
        # split data to multiple tx if exceeds size
        salt = None
        key = None
        if pw:
            text, salt, key = cls.encrypt(text, pw)
        # size-checking
        limit = TRANSACTION_SIZE_LIMITS[cls.chain.value]
        nr_of_transactions = cls.determine_nr_of_tx(text, limit)
        transaction_hashes = [""]*nr_of_transactions
        # if multiple transactions disabled
        if nr_of_transactions != 1 and not multiple_tx:
            raise TransactionSizeError
        # call original store method for each required tx separately
        for i in range(nr_of_transactions):
            subtext = text[i*limit:(i+1)*limit]
            transaction_hashes[i] = cls.store(subtext)
        return transaction_hashes, salt, key

    @classmethod
    def store(cls, text):
        # start = int(round(time.time() * 1000))  # Milliseconds
        transaction = cls.create_transaction(text)
        signed_transaction = cls.sign_transaction(transaction)
        transaction_hash = cls.send_raw_transaction(signed_transaction)

        # NOTE: originally DB interaction handled in store method itself
        # if(WAIT_FOR_CONFIRMATION):
        #     if(cls.confirmation_check(transaction_hash)):
        #         cls.add_transaction_to_database(transaction_hash)
        #         return transaction_hash
        #     else:
        #         raise LookupError(
        #             'Transaction not confirmed and not added to DB')
        # else:
        #     cls.add_transaction_to_database(transaction_hash)
        #     # cls.save_measurement(int(round(time.time() * 1000)) - start)
        #     return transaction_hash

        return transaction_hash

    @classmethod
    def confirmation_check(cls, transaction_hash):
        bc_id = cls.chain.value
        waiting_time = CONFIRMATION_WAITING_TIMES[bc_id]
        time.sleep(waiting_time)
        value = cls.retrieve(transaction_hash)
        if type(value) == str:
            return True
        else:
            return False

    @staticmethod
    @abstractmethod
    def create_transaction(text):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def sign_transaction(transaction):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def send_raw_transaction(transaction):
        raise NotImplementedError

    ##################
    # ---RETRIEVE--- #
    ##################
    @classmethod
    def retrieve_wrapper(cls, transaction_hashes, pw=None, salt=None, key=None):
        # wrapper function of original retrieve function
        # reconstruct data if split over multiple tx
        # perform decryption if pw, salt & key provided
        text = ""
        for i in range(len(transaction_hashes)):
            text += cls.retrieve(transaction_hashes[i])
        if pw and cls.verify_password(pw, salt, key):
            # only attempt decryption if pw matches
            # library throws error otherwise
            text = cls.decrypt(text, pw, salt, key)
        # there is potential to return an error instead of the encrypted text if pw fails verification
        return text

    @classmethod
    def retrieve(cls, transaction_hash):
        """Get the transaction data from a tx hash:
        Args:
            transaction_hash:   The transaction hash.
        Returns:
            string: The transaction data as text.
        """
        try:
            transaction = cls.get_transaction(transaction_hash)
        except Exception:
            raise TransactionNotFoundError
        data = cls.extract_data(transaction)
        return cls.to_text(data)

    @staticmethod
    @abstractmethod
    def get_transaction(transaction_hash):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def extract_data(transaction):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def to_text(data):
        raise NotImplementedError

    ####################
    # ---EVALUATION--- #
    ####################
    @classmethod
    def save_measurement(cls, measured_time):
        # remove this line after all data gathered
        print(f"This was measured: {measured_time}")
        bc_id = cls.chain.name
        with open(f"performance_test/data/{bc_id}.csv", 'a') as fd:
            fd.write(f"{measured_time},")
