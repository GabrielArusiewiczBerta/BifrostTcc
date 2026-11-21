import core_bifrost.net as net  # aplica a correção de IPv4 antes de qualquer chamada de rede
from core_bifrost.adapters.base_adapter import BaseAdapter
from core_bifrost.custom_errors import TransactionNotFoundError
from core_bifrost.testnet_keys import get_or_create_stellar_keypair
from core_bifrost.user_keys import resolve_user_secret

HORIZON_TESTNET_URL = "https://horizon-testnet.stellar.org"
FRIENDBOT_URL = "https://friendbot.stellar.org"


class StellarAdapter(BaseAdapter):
    NAME = "Stellar"
    MAX_SIZE = 28  # limite exato do campo memo_text da Stellar
    HASH_PREFIX = ""

    _server = None

    @classmethod
    def _horizon(cls):
        if cls._server is None:
            from stellar_sdk import Server
            cls._server = Server(horizon_url=HORIZON_TESTNET_URL)
        return cls._server

    @classmethod
    def _ensure_funded(cls, public_key: str):
        import requests
        from stellar_sdk.exceptions import NotFoundError

        server = cls._horizon()
        try:
            return server.load_account(public_key)
        except NotFoundError:
            requests.get(FRIENDBOT_URL, params={'addr': public_key}, timeout=30).raise_for_status()
            return server.load_account(public_key)

    @classmethod
    def store_chunk(cls, chunk: str, owner=None) -> str:
        if not net.real_network_enabled('STELLAR'):
            return super().store_chunk(chunk, owner=owner)

        from stellar_sdk import Asset, Keypair, Network, TransactionBuilder

        own_secret = resolve_user_secret(owner, 'STELLAR')
        keypair = Keypair.from_secret(own_secret) if own_secret else get_or_create_stellar_keypair()
        account = cls._ensure_funded(keypair.public_key)
        transaction = (
            TransactionBuilder(
                source_account=account,
                network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
                base_fee=100,
            )
            .add_text_memo(chunk)
            .append_payment_op(destination=keypair.public_key, asset=Asset.native(), amount='0.0000001')
            .set_timeout(30)
            .build()
        )
        transaction.sign(keypair)
        response = cls._horizon().submit_transaction(transaction)
        return response['hash']

    @classmethod
    def retrieve_chunk(cls, tx_hash: str) -> str:
        if not net.real_network_enabled('STELLAR'):
            return super().retrieve_chunk(tx_hash)

        from stellar_sdk.exceptions import NotFoundError

        try:
            record = cls._horizon().transactions().transaction(tx_hash).call()
        except NotFoundError:
            raise TransactionNotFoundError(f"Transação {tx_hash} não encontrada na Stellar Testnet.")
        memo = record.get('memo')
        if memo is None:
            raise TransactionNotFoundError(f"Transação {tx_hash} não tem memo_text (não foi gravada pelo NodeConnect).")
        return memo
