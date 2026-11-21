import base64
import hashlib
import hmac
import os

from cryptography.fernet import Fernet, InvalidToken

from core_bifrost.custom_errors import DecryptionError

ITERATIONS = 100_000


def _derive_keys(password: str, salt: bytes):
    """key_1 serve para verificar a senha; key_2 (derivada de senha + key_1) cifra os dados."""
    pw = password.encode('utf-8')
    key_1 = base64.urlsafe_b64encode(hashlib.pbkdf2_hmac('sha256', pw, salt, ITERATIONS, 32))
    key_2 = base64.urlsafe_b64encode(hashlib.pbkdf2_hmac('sha256', pw + key_1, salt, ITERATIONS, 32))
    return key_1, key_2


def _verifier(key_1: bytes) -> str:
    return hashlib.sha256(key_1).hexdigest()


def encrypt_payload(data: str, password: str):
    """Cifra com Fernet. Retorna (token, salt_hex, verificador_da_senha)."""
    salt = os.urandom(16)
    key_1, key_2 = _derive_keys(password, salt)
    token = Fernet(key_2).encrypt(data.encode('utf-8')).decode('ascii')
    return token, salt.hex(), _verifier(key_1)


def decrypt_payload(token: str, password: str, salt: str, verifier: str) -> str:
    """Decifra. Levanta DecryptionError se a senha estiver errada ou o dado estiver corrompido."""
    key_1, key_2 = _derive_keys(password, bytes.fromhex(salt))
    if not hmac.compare_digest(_verifier(key_1), verifier):
        raise DecryptionError('Senha incorreta.')
    try:
        return Fernet(key_2).decrypt(token.encode('ascii')).decode('utf-8')
    except InvalidToken:
        raise DecryptionError('Dado corrompido ou incompleto: não foi possível decifrar.')
