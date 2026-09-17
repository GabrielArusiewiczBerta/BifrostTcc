import hashlib
import uuid
from core_bifrost.custom_errors import TransactionSizeError
from core_bifrost.crypto_utils import encrypt_payload, decrypt_payload

class BaseAdapter:
    NAME = "Base"
    MAX_SIZE = 1000  # Max bytes allowed per single transaction payload

    @classmethod
    def store_wrapper(cls, text: str, pw: str = None, multiple_tx: bool = False):
        salt = ""
        key = ""
        if pw:
            text, salt, key = encrypt_payload(text, pw)
            
        data_bytes = text.encode('utf-8')
        if len(data_bytes) > cls.MAX_SIZE and not multiple_tx:
            raise TransactionSizeError(
                f"Tamanho dos dados ({len(data_bytes)} bytes) excede o limite máximo por transação "
                f"da blockchain {cls.NAME} ({cls.MAX_SIZE} bytes). Ative 'multiple_tx=True' para permitir fragmentação."
            )
            
        # Fragment text if needed
        chunks = []
        if len(data_bytes) > cls.MAX_SIZE:
            for i in range(0, len(text), cls.MAX_SIZE):
                chunks.append(text[i:i + cls.MAX_SIZE])
        else:
            chunks = [text]
            
        hashes = []
        for chunk in chunks:
            tx_hash = cls.store_chunk(chunk)
            hashes.append(tx_hash)
            
        return hashes, salt, key

    @classmethod
    def store_chunk(cls, chunk: str) -> str:
        # Override in specific adapters
        tx_hash = hashlib.sha256(f"{cls.NAME}:{uuid.uuid4()}:{chunk}".encode('utf-8')).hexdigest()
        return tx_hash

    @classmethod
    def retrieve_wrapper(cls, transaction_hashes: list, pw: str = None, salt: str = None, key: str = None):
        combined_text = ""
        for tx_hash in transaction_hashes:
            chunk = cls.retrieve_chunk(tx_hash)
            combined_text += chunk
            
        if pw and salt:
            combined_text = decrypt_payload(combined_text, pw, salt)
            
        return combined_text

    @classmethod
    def retrieve_chunk(cls, tx_hash: str) -> str:
        # Override in specific adapters
        return f"[Data retrieved for tx {tx_hash[:10]}]"
