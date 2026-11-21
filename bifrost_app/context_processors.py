from core_bifrost.net import real_network_enabled

REAL_CAPABLE_NETWORKS = ['STELLAR', 'BITCOIN', 'ETHEREUM']


def real_networks(request):
    """Disponibiliza em todos os templates quais redes reais estão ativas (BIFROST_REAL_NETWORKS)."""
    active = [code for code in REAL_CAPABLE_NETWORKS if real_network_enabled(code)]
    return {'real_networks_enabled': active}
