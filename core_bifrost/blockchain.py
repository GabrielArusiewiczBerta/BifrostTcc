from enum import Enum

class Blockchain(Enum):
    ETHEREUM = 1
    MULTICHAIN = 2
    BITCOIN = 3
    POSTGRES = 4
    STELLAR = 5
    HYPERLEDGER = 6
    EOS = 7
    IOTA = 8
    RBB = 9  # Rede Blockchain Brasil

    @classmethod
    def from_name(cls, name_str):
        name_clean = str(name_str).upper().strip()
        for bc in cls:
            if bc.name == name_clean or str(bc.value) == name_clean:
                return bc
        raise ValueError(f"Blockchain desconhecida: {name_str}")
