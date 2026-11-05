import core_bifrost.net as net  # aplica a correção de IPv4 antes de qualquer chamada de rede
from core_bifrost.adapters.base_adapter import BaseAdapter
from core_bifrost.custom_errors import TransactionNotFoundError
from core_bifrost.testnet_keys import get_or_create_btc_key
from core_bifrost.user_keys import resolve_user_secret

ESPLORA_TESTNET_URL = "https://blockstream.info/testnet/api"
DEFAULT_FEE_RATE_SAT_VB = 2  # usado se a API de estimativa de taxa falhar


class BTCAdapter(BaseAdapter):
    NAME = "Bitcoin"
    MAX_SIZE = 80  # limite padrão de um único OP_RETURN
    HASH_PREFIX = ""

    # Cache em memória do último troco conhecido, por endereço (evita reconsultar a API
    # pública entre fragmentos da mesma operação: o índice dela demora um pouco pra refletir
    # nosso próprio broadcast, e reconsultar cedo demais devolve o UTXO que acabamos de gastar,
    # causando "gasto duplicado" na rede). Por endereço porque, com chave própria por usuário
    # (core_bifrost/user_keys.py), cada carteira tem seu próprio troco. Limpo por endereço
    # sempre que um broadcast daquele endereço falha.
    _cached_utxo_by_address = {}

    @classmethod
    def _fee_rate(cls):
        import requests
        try:
            rates = requests.get(f"{ESPLORA_TESTNET_URL}/fee-estimates", timeout=15).json()
            # Na testnet a estimativa por alvo de confirmação é instável (picos de até 250+
            # sat/vB sem congestionamento real, provavelmente por poucos blocos recentes
            # amostrados). Usar o mínimo entre todos os alvos evita pagar um pico artificial.
            return max(1, round(min(rates.values()))) if rates else DEFAULT_FEE_RATE_SAT_VB
        except Exception:
            return DEFAULT_FEE_RATE_SAT_VB

    @classmethod
    def _next_utxo(cls, address_str):
        import requests

        cached = cls._cached_utxo_by_address.get(address_str)
        if cached is not None:
            return cached

        utxos = requests.get(f"{ESPLORA_TESTNET_URL}/address/{address_str}/utxo", timeout=15).json()
        if not utxos:
            raise ValueError(
                f"Conta Bitcoin Testnet ({address_str}) sem saldo. "
                f"Financie via uma faucet de testnet antes de gravar."
            )
        return max(utxos, key=lambda u: u['value'])

    @classmethod
    def store_chunk(cls, chunk: str, owner=None) -> str:
        if not net.real_network_enabled('BITCOIN'):
            return super().store_chunk(chunk, owner=owner)

        import requests
        from bitcoinutils.setup import setup
        from bitcoinutils.keys import PrivateKey
        from bitcoinutils.script import Script
        from bitcoinutils.transactions import Transaction, TxInput, TxOutput, TxWitnessInput

        own_wif = resolve_user_secret(owner, 'BITCOIN')
        if own_wif:
            setup('testnet')
            private_key = PrivateKey(own_wif)
        else:
            private_key = get_or_create_btc_key()
        public_key = private_key.get_public_key()
        address = public_key.get_segwit_address()
        data = chunk.encode('utf-8')

        utxo = cls._next_utxo(address.to_string())
        fee_rate = cls._fee_rate()
        estimated_vsize = 110 + len(data)  # 1 entrada P2WPKH + troco + OP_RETURN (aprox.)
        fee = fee_rate * estimated_vsize
        if utxo['value'] < fee:
            cls._cached_utxo_by_address.pop(address.to_string(), None)
            raise ValueError(
                f"Saldo insuficiente na conta Bitcoin Testnet ({address.to_string()}) para cobrir a taxa estimada."
            )

        script_code = Script(['OP_DUP', 'OP_HASH160', public_key.to_hash160(), 'OP_EQUALVERIFY', 'OP_CHECKSIG'])
        txin = TxInput(utxo['txid'], utxo['vout'])
        op_return_output = TxOutput(0, Script(['OP_RETURN', data.hex()]))
        change_value = utxo['value'] - fee
        change_output = TxOutput(change_value, address.to_script_pub_key())

        tx = Transaction([txin], [op_return_output, change_output], has_segwit=True)
        # utxo['value'] já vem em satoshis (convenção da API Esplora), sem conversão adicional.
        signature = private_key.sign_segwit_input(tx, 0, script_code, utxo['value'])
        tx.witnesses.append(TxWitnessInput([signature, public_key.to_hex()]))

        response = requests.post(f"{ESPLORA_TESTNET_URL}/tx", data=tx.serialize(), timeout=30)
        if not response.ok:
            cls._cached_utxo_by_address.pop(address.to_string(), None)  # pode estar desatualizado; força reconsulta na próxima tentativa
            response.raise_for_status()

        tx_hash = response.text.strip()
        cls._cached_utxo_by_address[address.to_string()] = {'txid': tx_hash, 'vout': 1, 'value': change_value}
        return tx_hash

    @classmethod
    def retrieve_chunk(cls, tx_hash: str) -> str:
        if not net.real_network_enabled('BITCOIN'):
            return super().retrieve_chunk(tx_hash)

        import requests

        response = requests.get(f"{ESPLORA_TESTNET_URL}/tx/{tx_hash}", timeout=15)
        if response.status_code == 404:
            raise TransactionNotFoundError(f"Transação {tx_hash} não encontrada na Bitcoin Testnet.")
        response.raise_for_status()
        outputs = response.json().get('vout', [])
        op_return = next((o for o in outputs if o.get('scriptpubkey_type') == 'op_return'), None)
        if op_return is None:
            raise TransactionNotFoundError(f"Transação {tx_hash} não tem saída OP_RETURN (não foi gravada pelo NodeConnect).")

        raw = bytes.fromhex(op_return['scriptpubkey'])
        if raw[1] == 0x4c:  # OP_PUSHDATA1: próximo byte é o tamanho
            data = raw[3:3 + raw[2]]
        else:  # push direto: o próprio opcode é o tamanho
            data = raw[2:2 + raw[1]]
        return data.decode('utf-8')
