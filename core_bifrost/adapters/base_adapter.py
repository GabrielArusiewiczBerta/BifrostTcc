import hashlib
import uuid
import core_bifrost.db_manager as db
from core_bifrost.custom_errors import TransactionSizeError
from core_bifrost.crypto_utils import encrypt_payload, decrypt_payload


def split_by_bytes(text: str, limit: int):
    """Divide o texto em pedaços de no máximo `limit` bytes UTF-8, sem quebrar caracteres."""
    chunks, current, size = [], [], 0
    for ch in text:
        n = len(ch.encode('utf-8'))
        if n > limit:
            raise TransactionSizeError(f"O limite de {limit} bytes por transação é menor que um único caractere.")
        if size + n > limit:
            chunks.append(''.join(current))
            current, size = [], 0
        current.append(ch)
        size += n
    if current:
        chunks.append(''.join(current))
    return chunks


class BaseAdapter:
    NAME = "Base"
    MAX_SIZE = 1000  # bytes por transação
    HASH_PREFIX = ""

    @classmethod
    def store_wrapper(cls, text: str, pw: str = None, multiple_tx: bool = False, owner=None):
        salt = ""
        key = ""
        if pw:
            text, salt, key = encrypt_payload(text, pw)

        chunks = split_by_bytes(text, cls.MAX_SIZE)
        if len(chunks) > 1 and not multiple_tx:
            raise TransactionSizeError(
                f"Tamanho dos dados ({len(text.encode('utf-8'))} bytes) excede o limite máximo por transação "
                f"da blockchain {cls.NAME} ({cls.MAX_SIZE} bytes). Ative 'multiple_tx=True' para permitir fragmentação."
            )

        hashes = [cls.store_chunk(chunk, owner=owner) for chunk in chunks]
        return hashes, salt, key

    @classmethod
    def store_chunk(cls, chunk: str, owner=None) -> str:
        """Simulação: grava no ledger local. Adaptadores reais sobrescrevem este método.
        `owner` (dono da operação) é ignorado aqui; adaptadores reais o usam para decidir
        entre a chave de blockchain própria do usuário ou a chave central (core_bifrost/user_keys.py)."""
        tx_hash = cls.HASH_PREFIX + hashlib.sha256(f"{cls.__name__}:{uuid.uuid4()}:{chunk}".encode('utf-8')).hexdigest()
        db.sim_put(tx_hash, cls.__name__, chunk)
        return tx_hash

    @classmethod
    def retrieve_wrapper(cls, transaction_hashes: list, pw: str = None, salt: str = None, key: str = None):
        combined_text = "".join(cls.retrieve_chunk(h) for h in transaction_hashes)
        if pw and salt:
            combined_text = decrypt_payload(combined_text, pw, salt, key)
        return combined_text

    @classmethod
    def retrieve_chunk(cls, tx_hash: str) -> str:
        """Simulação: lê do ledger local. Levanta TransactionNotFoundError se não existir."""
        return db.sim_get(tx_hash, cls.__name__)
