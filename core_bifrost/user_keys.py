"""Permite que os adaptadores reais usem uma chave de blockchain própria do usuário,
em vez da chave central (testnet_keys.py), quando o usuário tiver cadastrado uma.

core_bifrost não conhece o Django (motor independente, ver CLAUDE.md): quem resolve
a chave é um resolvedor registrado pela camada web (bifrost_app) na inicialização
(bifrost_app/apps.py). Sem resolvedor registrado, ou sem chave própria para aquele
usuário/blockchain, todos caem de volta na chave central como antes.
"""
_resolver = None  # callable(owner, blockchain_code: str) -> str (segredo em claro) | None


def register_resolver(fn):
    global _resolver
    _resolver = fn


def resolve_user_secret(owner, blockchain_code: str):
    if _resolver is None or owner is None:
        return None
    return _resolver(owner, blockchain_code)
