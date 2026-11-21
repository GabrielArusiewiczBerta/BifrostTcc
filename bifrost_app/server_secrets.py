"""Cifra em repouso as chaves de blockchain próprias do usuário (UserBlockchainKey).

Diferente do password de store/retrieve (core_bifrost/crypto_utils.py, derivado da senha
do próprio usuário), aqui não existe senha: a chave só precisa ser legível pelo servidor
pra assinar transações em nome do dono dela. Por isso usa Fernet com uma chave derivada
do SECRET_KEY do Django (mesmo segredo que já protege sessão e cookies assinados).
"""
import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings


def _fernet() -> Fernet:
    derived = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_secret(raw: str) -> str:
    return _fernet().encrypt(raw.encode('utf-8')).decode('ascii')


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode('ascii')).decode('utf-8')
