"""Chaves de teste para as redes reais (Stellar Testnet, Bitcoin Testnet, Ethereum Sepolia).

Mesmo padrão do SECRET_KEY do Django (bifrost_project/settings.py): variável de
ambiente tem prioridade; senão usa (ou cria) um arquivo local fora do git,
com permissão 600. Nunca são chaves de valor real — apenas identidades de testnet.
"""
import json
from pathlib import Path

KEYS_FILE = Path(__file__).resolve().parent.parent / '.testnet_keys.json'


def _load_local_keys() -> dict:
    if KEYS_FILE.exists():
        return json.loads(KEYS_FILE.read_text())
    return {}


def _save_local_keys(data: dict) -> None:
    KEYS_FILE.write_text(json.dumps(data, indent=2))
    KEYS_FILE.chmod(0o600)


def generate_stellar_keypair():
    """Gera um stellar_sdk.Keypair novo, sem persistir em lugar nenhum (quem chamar decide)."""
    from stellar_sdk import Keypair
    return Keypair.random()


def get_or_create_stellar_keypair():
    """Devolve um stellar_sdk.Keypair. Usa BIFROST_STELLAR_SECRET se definida,
    senão gera (ou reaproveita) uma chave local. A conta pode não estar
    financiada ainda: quem chamar decide se financia via Friendbot."""
    import os
    from stellar_sdk import Keypair

    env_secret = os.environ.get('BIFROST_STELLAR_SECRET')
    if env_secret:
        return Keypair.from_secret(env_secret)

    keys = _load_local_keys()
    stored = keys.get('stellar')
    if stored:
        return Keypair.from_secret(stored['secret'])

    keypair = generate_stellar_keypair()
    keys['stellar'] = {'public': keypair.public_key, 'secret': keypair.secret}
    _save_local_keys(keys)
    return keypair


def generate_btc_key():
    """Gera uma bitcoinutils.keys.PrivateKey nova (rede testnet), sem persistir."""
    from bitcoinutils.setup import setup
    from bitcoinutils.keys import PrivateKey

    setup('testnet')
    return PrivateKey()


def get_or_create_btc_key():
    """Devolve uma bitcoinutils.keys.PrivateKey (rede testnet). Usa BIFROST_BTC_WIF se
    definida, senão gera (ou reaproveita) uma chave local. Pode estar sem saldo: quem
    chamar decide se financia via faucet."""
    import os
    from bitcoinutils.setup import setup
    from bitcoinutils.keys import PrivateKey

    setup('testnet')

    env_wif = os.environ.get('BIFROST_BTC_WIF')
    if env_wif:
        return PrivateKey(env_wif)

    keys = _load_local_keys()
    stored = keys.get('bitcoin')
    if stored:
        return PrivateKey(stored['wif'])

    private_key = generate_btc_key()
    address = private_key.get_public_key().get_segwit_address().to_string()
    keys['bitcoin'] = {'address': address, 'wif': private_key.to_wif()}
    _save_local_keys(keys)
    return private_key


def generate_eth_account():
    """Gera uma eth_account.Account (LocalAccount) nova, sem persistir."""
    from eth_account import Account
    return Account.create()


def get_or_create_eth_account():
    """Devolve uma eth_account.Account (LocalAccount). Usa BIFROST_ETH_PRIVATE_KEY
    se definida, senão gera (ou reaproveita) uma conta local. Pode estar sem saldo:
    quem chamar decide se financia via faucet."""
    import os
    from eth_account import Account

    env_key = os.environ.get('BIFROST_ETH_PRIVATE_KEY')
    if env_key:
        return Account.from_key(env_key)

    keys = _load_local_keys()
    stored = keys.get('ethereum')
    if stored:
        return Account.from_key(stored['private_key'])

    account = generate_eth_account()
    keys['ethereum'] = {'address': account.address, 'private_key': account.key.hex()}
    _save_local_keys(keys)
    return account
