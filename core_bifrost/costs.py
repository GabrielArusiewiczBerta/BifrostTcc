"""Calculadora de custo para gravar dados em cada blockchain (fórmulas fechadas).

O custo é o equivalente na mainnet: nas testnets o token não tem valor, mas o consumo
(gas, vbytes, operações) é o mesmo. Preços e taxas abaixo são referências ajustáveis,
não cotações ao vivo.

Fórmulas:
- Ethereum (EIP-2028 + EIP-7623): gas = max(21000 + 16*nz + 4*z, 21000 + 10*(z + 4*nz)),
  onde z = bytes zero e nz = bytes não zero do calldata; taxa = gas * preço_do_gas.
- Bitcoin (OP_RETURN, 1 entrada P2WPKH, 1 saída de troco P2WPKH):
  vsize = ceil(10,5 + 68 + 31 + (8 + 1 + 1 + push + n)), push = 1 se n <= 75, senão 2;
  taxa = vsize * sat/vB.
- Stellar: taxa = operações * taxa_base (100 stroops); o memo não custa a mais.
- EOS: sem taxa por transação (modelo de recursos); NET ~ (base + n) arredondado a 8 bytes (aproximado).
- RBB (Besu permissionada), MultiChain e PostgreSQL: sem taxa por transação.
- Criptografia (Fernet): token = 4 * ceil((57 + 16 * (n // 16 + 1)) / 3) bytes, para n bytes de texto.
"""
import math

from core_bifrost.adapters.base_adapter import split_by_bytes
from core_bifrost.api import AdapterRegistry, identify_blockchain
from core_bifrost.blockchain import Blockchain

DEFAULT_PARAMS = {
    'gas_price_gwei': 5.0,
    'fee_rate_sat_vb': 10.0,
    'stellar_base_fee_stroops': 100.0,
    'usd_prices': {'ETH': 3000.0, 'BTC': 60000.0, 'XLM': 0.12, 'EOS': 0.7},
}

NATIVE_SYMBOL = {
    Blockchain.ETHEREUM: 'ETH',
    Blockchain.BITCOIN: 'BTC',
    Blockchain.STELLAR: 'XLM',
    Blockchain.EOS: 'EOS',
    Blockchain.RBB: 'RBB',
    Blockchain.MULTICHAIN: 'MC',
    Blockchain.POSTGRES: '-',
}

EOS_BASE_TX_BYTES = 128
ETH_BASE_GAS = 21000


def symbol_for(blockchain_name: str) -> str:
    return NATIVE_SYMBOL.get(Blockchain.from_name(blockchain_name), '-')


def fernet_token_size(n: int) -> int:
    return 4 * math.ceil((57 + 16 * (n // 16 + 1)) / 3)


def eth_gas(n: int, zero_bytes: int = 0) -> int:
    nonzero = n - zero_bytes
    standard = ETH_BASE_GAS + 16 * nonzero + 4 * zero_bytes
    floor = ETH_BASE_GAS + 10 * (zero_bytes + 4 * nonzero)
    return max(standard, floor)


def btc_vsize(n: int) -> int:
    push = 1 if n <= 75 else 2
    return math.ceil(10.5 + 68 + 31 + (8 + 1 + 1 + push + n))


def resolve_params(overrides=None) -> dict:
    """Mescla os padrões com ajustes do usuário, validando faixa e tipo."""
    params = {**DEFAULT_PARAMS, 'usd_prices': dict(DEFAULT_PARAMS['usd_prices'])}
    overrides = overrides or {}
    limits = {'gas_price_gwei': 1e6, 'fee_rate_sat_vb': 1e6, 'stellar_base_fee_stroops': 1e9}
    for key, upper in limits.items():
        if overrides.get(key) not in (None, ''):
            params[key] = _positive_float(overrides[key], key, upper)
    for symbol, value in (overrides.get('usd_prices') or {}).items():
        if symbol in params['usd_prices'] and value not in (None, ''):
            params['usd_prices'][symbol] = _positive_float(value, f'preço {symbol}', 1e9)
    return params


def _positive_float(value, name, upper):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'Valor inválido para {name}.')
    if not math.isfinite(number) or number < 0 or number > upper:
        raise ValueError(f'Valor fora da faixa permitida para {name}.')
    return number


def _fragment_sizes(text, size, limit, encrypted):
    if text is not None and not encrypted:
        return [len(c.encode('utf-8')) for c in split_by_bytes(text, limit)]
    full, rest = divmod(size, limit)
    return [limit] * full + ([rest] if rest else [])


def _tx_fee(blockchain, size, zero_bytes, params):
    """Retorna (taxa em unidade nativa, detalhes) para uma transação com `size` bytes de dado."""
    if blockchain == Blockchain.ETHEREUM:
        gas = eth_gas(size, zero_bytes)
        return gas * params['gas_price_gwei'] * 1e-9, {'gas': gas}
    if blockchain == Blockchain.BITCOIN:
        vsize = btc_vsize(size)
        return vsize * params['fee_rate_sat_vb'] / 1e8, {'vbytes': vsize}
    if blockchain == Blockchain.STELLAR:
        stroops = params['stellar_base_fee_stroops']
        return stroops / 1e7, {'operacoes': 1}
    if blockchain == Blockchain.EOS:
        net = math.ceil((EOS_BASE_TX_BYTES + size) / 8) * 8
        return 0.0, {'net_bytes': net}
    if blockchain == Blockchain.RBB:
        return 0.0, {'gas': eth_gas(size, zero_bytes)}
    return 0.0, {}


PRECISION = {
    Blockchain.ETHEREUM: 'exata (unidades de gas); preço do gas é parâmetro',
    Blockchain.BITCOIN: 'exata para 1 entrada P2WPKH; taxa em sat/vB é parâmetro',
    Blockchain.STELLAR: 'exata (taxa base por operação)',
    Blockchain.EOS: 'aproximada (modelo de recursos, sem taxa por transação)',
    Blockchain.RBB: 'sem taxa (rede permissionada)',
    Blockchain.MULTICHAIN: 'sem taxa (rede privada)',
    Blockchain.POSTGRES: 'sem taxa (banco de dados)',
}


def estimate(blockchain, payload=None, size_bytes=None, encrypted=False, multiple_tx=False, params=None):
    """Estima o custo de gravar o dado numa blockchain. Informe `payload` (texto) ou `size_bytes`."""
    if isinstance(blockchain, str):
        blockchain = Blockchain.from_name(blockchain)
    adapter = identify_blockchain(blockchain)
    params = params if params is not None else resolve_params()

    if payload is not None:
        raw_bytes = len(payload.encode('utf-8'))
        zero_bytes = payload.count('\0')
    elif size_bytes is not None:
        raw_bytes, zero_bytes = int(size_bytes), 0
    else:
        raise ValueError('Informe o conteúdo ou o tamanho em bytes.')
    if raw_bytes <= 0:
        raise ValueError('O conteúdo deve ter pelo menos 1 byte.')

    onchain_bytes = fernet_token_size(raw_bytes) if encrypted else raw_bytes
    if encrypted:
        zero_bytes = 0
    sizes = _fragment_sizes(payload, onchain_bytes, adapter.MAX_SIZE, encrypted)

    total_native, details = 0.0, {}
    for size in sizes:
        fee, detail = _tx_fee(blockchain, size, zero_bytes if len(sizes) == 1 else 0, params)
        total_native += fee
        for key, value in detail.items():
            details[key] = details.get(key, 0) + value

    symbol = NATIVE_SYMBOL.get(blockchain, '-')
    price = params['usd_prices'].get(symbol, 0.0)
    feasible = len(sizes) == 1 or multiple_tx
    return {
        'blockchain': blockchain.name,
        'name': adapter.NAME,
        'symbol': symbol,
        'payload_bytes': raw_bytes,
        'onchain_bytes': onchain_bytes,
        'encrypted': encrypted,
        'max_size': adapter.MAX_SIZE,
        'fragments': len(sizes),
        'feasible': feasible,
        'note': None if feasible else 'Excede o limite por transação: ative multiple_tx (fragmentação).',
        'fee_native': total_native,
        'fee_usd': total_native * price,
        'details': details,
        'precision': PRECISION.get(blockchain, ''),
    }


def estimate_all(payload=None, size_bytes=None, encrypted=False, multiple_tx=False, params=None):
    """Compara todas as redes, da mais barata (USD) para a mais cara."""
    params = params if params is not None else resolve_params()
    results = [
        estimate(chain, payload, size_bytes, encrypted, multiple_tx, params)
        for chain in AdapterRegistry
    ]
    return sorted(results, key=lambda r: (r['fee_usd'], r['fragments']))
