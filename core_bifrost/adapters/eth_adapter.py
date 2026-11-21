import core_bifrost.net as net  # aplica a correção de IPv4 antes de qualquer chamada de rede
from core_bifrost.adapters.base_adapter import BaseAdapter
from core_bifrost.custom_errors import TransactionNotFoundError
from core_bifrost.testnet_keys import get_or_create_eth_account
from core_bifrost.user_keys import resolve_user_secret

SEPOLIA_RPC_URL = "https://ethereum-sepolia-rpc.publicnode.com"
SEPOLIA_CHAIN_ID = 11155111


class EthAdapter(BaseAdapter):
    NAME = "Ethereum"
    MAX_SIZE = 1024  # limite prático de calldata por transação (gas)
    HASH_PREFIX = "0x"

    _web3 = None

    @classmethod
    def _rpc(cls):
        if cls._web3 is None:
            from web3 import Web3
            cls._web3 = Web3(Web3.HTTPProvider(SEPOLIA_RPC_URL, request_kwargs={'timeout': 30}))
        return cls._web3

    @classmethod
    def store_chunk(cls, chunk: str, owner=None) -> str:
        if not net.real_network_enabled('ETHEREUM'):
            return super().store_chunk(chunk, owner=owner)

        from eth_account import Account

        w3 = cls._rpc()
        own_key = resolve_user_secret(owner, 'ETHEREUM')
        account = Account.from_key(own_key) if own_key else get_or_create_eth_account()
        data = chunk.encode('utf-8')

        tx = {
            'from': account.address,
            'to': account.address,
            'value': 0,
            'data': data,
            'nonce': w3.eth.get_transaction_count(account.address, 'pending'),
            'chainId': SEPOLIA_CHAIN_ID,
        }
        tx['gas'] = w3.eth.estimate_gas(tx)
        tx['gasPrice'] = w3.eth.gas_price

        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        return '0x' + tx_hash.hex().removeprefix('0x')

    @classmethod
    def retrieve_chunk(cls, tx_hash: str) -> str:
        if not net.real_network_enabled('ETHEREUM'):
            return super().retrieve_chunk(tx_hash)

        from web3.exceptions import TransactionNotFound

        try:
            transaction = cls._rpc().eth.get_transaction(tx_hash)
        except TransactionNotFound:
            raise TransactionNotFoundError(f"Transação {tx_hash} não encontrada na Ethereum Sepolia.")
        return bytes(transaction['input']).decode('utf-8')
