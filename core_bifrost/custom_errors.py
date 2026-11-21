class TransactionSizeError(Exception):
    """Raised when data exceeds single transaction payload limit and multiple_tx is False"""
    pass

class TransactionNotFoundError(Exception):
    """Raised when transaction hash is not found in local database or on-chain"""
    pass

class BlockchainNotFoundError(Exception):
    """Raised when requested blockchain adapter is not supported or registered"""
    pass

class DecryptionError(Exception):
    """Raised when password/key is invalid for decrypting payload"""
    pass
