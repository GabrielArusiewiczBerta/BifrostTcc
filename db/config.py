from blockchain import Blockchain
import os

AMOUNT = 0
ENCODING = 'utf-8'
# DATABASE_PATH = 'db/bcio.db'
DATABASE_PATH = os.path.dirname(os.path.realpath(__file__)) + '/bcio.db'
# NOTE: need entire path, else all db accesses fail if not made from
#  file within repo root folder. This fix works as LONG AS
#  'config.py' and the db are in the same directory
WAIT_FOR_CONFIRMATION = False

# Set how long to wait until checking if tx arrived
CONFIRMATION_WAITING_TIMES = {
    Blockchain.ETHEREUM.value: max(105, 20),
    Blockchain.MULTICHAIN.value: max(15, 20),
    Blockchain.BITCOIN.value: max(3600, 20),
    Blockchain.POSTGRES.value: max(5, 20),
    Blockchain.STELLAR.value: max(5, 20),
    Blockchain.HYPERLEDGER.value: max(20, 20),
    Blockchain.EOS.value: max(0.5, 20),
    Blockchain.IOTA.value: max(60, 20),
}

# tx size limits in bytes
# NOTE: some of the limits are not actually static in reality
TRANSACTION_SIZE_LIMITS = {
    Blockchain.BITCOIN.value: 80,
    Blockchain.ETHEREUM.value: 46000,
    Blockchain.POSTGRES.value: 100000,
    # 100kb for now, "unlimited"
    Blockchain.STELLAR.value: 28,
    Blockchain.EOS.value: 256,
    Blockchain.IOTA.value: 1300,
    Blockchain.HYPERLEDGER.value: 20,
    Blockchain.MULTICHAIN.value: 80
}

CREDENTIALS = [
    {
        "blockchain": Blockchain.ETHEREUM.name,
        "id": Blockchain.ETHEREUM.value,

        # DEFAULT
        # "key": '',
        # "address": '',

        # GANACHE
        # "address": '0x9186d22defb55099C633FC010efE4f6abbF63a42',
        # "key": 'd3bc2fdc00b3e09796cfcdee81d07faa2894686d470a5164e324659d8c5c5bea',

        # DOCKER
        "address": '0xF717E2D05037D13d6BFd0d783d6f4ebd68Dd5B46',
        "key": '0xec7a5eb646075cc16dd842381489614a49eda87e1f600d8780bbb3012288a98f',

        "user": 'ethereum (not used)',
        "password": 'ethereum (not used)',
    },
    {
        "blockchain": Blockchain.MULTICHAIN,
        "id": Blockchain.MULTICHAIN.value,
        "address": '',
        "key": '',
        "user": 'multichainrpc',
        "password": ''
    },
    {
        "blockchain": Blockchain.BITCOIN,
        "id": Blockchain.BITCOIN.value,
        "address": '',
        "key": '',
        "user": '',
        "password": ''
    },
    {
        "blockchain": Blockchain.POSTGRES,
        "id": Blockchain.POSTGRES.value,
        # database name
        "address": 'test',
        # port number
        "key": '5000',
        "user": 'test',
        "password": '123456'
    },
    {
        "blockchain": Blockchain.STELLAR,
        "id": Blockchain.STELLAR.value,
        "address": 'GAZDOJO6HTOMLPOWBGG5YXKQ4IN7GMOSI3E3R7OCBJJ6F3YM4W3KB6FQ',
        "key": 'SDWNHC5DGHDW5SJB3EYRSCHECVMXOE4OOE465GX6Y3SY622NBHA2APFX',
        "user": 'stellar (not used)',
        "password": 'stellar (not used)'
    },
    {
        "blockchain": Blockchain.HYPERLEDGER,
        "id": Blockchain.HYPERLEDGER.value,
        "address": 'will be generated from private key',
        "key": '',
        "user": 'hyperledger (not used)',
        "password": 'hyperledger (not used)'
    },
    {
        "blockchain": Blockchain.EOS,
        "id": Blockchain.EOS.value,
        "address": 'EOS5PAuxxndfa4fkLwkcJXNHfNtNCWSU1XQp8Ev2SqRNvKRGvJzcV',
        "key": '5JtJip9U76ndN4DWPrpv6qrLR6m4ojGNJ6zeWKMonVfq1PTVM3r',
        "user": 'asdf1234fdsa',
        "password": 'eos (not used)'
    },
    {
        "blockchain": Blockchain.IOTA,
        "id": Blockchain.IOTA.value,
        "address": '',
        "key": 'iota (not used)',
        "user": 'iota (not used)',
        "password": 'iota (not used)',
    }
]
TRANSACTIONS = [
    ## just for BCs that are UTXO, since UTXO needed for tx on these
    ## so this simulates the first unspent outputs
    ## - for BC tx-hash from Docker
    ## - for Multichain also from Docker and "some commments"

    {
        "blockchain": Blockchain.MULTICHAIN.value,
        # "transaction_hash": '',
        "transaction_hash": '123',
    },
    {
        "blockchain": Blockchain.BITCOIN.value,
        # "transaction_hash": '',
        "transaction_hash": '456',
    }
]

