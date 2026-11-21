"""Ajustes de rede compartilhados pelos adaptadores que falam com redes reais.

Em várias redes/VMs o IPv6 está "habilitado" no sistema mas não tem rota de saída.
`requests`/`urllib3` (usados por `web3.py` e `stellar-sdk`) resolvem o host, pegam o
primeiro endereço (às vezes IPv6) e travam no connect() até o timeout do SO, bem mais
longo que o timeout do request. `curl` não tem esse problema porque já faz
Happy Eyeballs (tenta IPv4 e IPv6 em paralelo). A correção é forçar a resolução para
IPv4, aplicada uma única vez, na importação deste módulo.
"""
import os
import socket

import urllib3.util.connection as _urllib3_connection

_urllib3_connection.allowed_gai_family = lambda: socket.AF_INET


def real_network_enabled(blockchain_code: str) -> bool:
    """True se a rede deve falar com a testnet de verdade em vez de simular.
    Controlado por BIFROST_REAL_NETWORKS="STELLAR,ETHEREUM" (vazio por padrão,
    ou seja, tudo simulado, mantendo o comportamento e os testes de sempre)."""
    enabled = os.environ.get('BIFROST_REAL_NETWORKS', '')
    codes = {c.strip().upper() for c in enabled.split(',') if c.strip()}
    return blockchain_code.upper() in codes
