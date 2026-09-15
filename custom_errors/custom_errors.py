from enum import Enum, auto


# Define enum with custom errors
class CustomErrors(Enum):
    TX_SIZE_ERROR = auto()
    TX_NOT_FOUND_ERROR = auto()
    BC_NOT_FOUND_ERROR = auto()
    INVALID_PASSWORD_ERROR = auto()  # NOTE: not currently used, simply returns encrypted data
    GENERIC_ERROR = auto()  # NOTE: not currently used, meant to be used for internal server error


# Define Error Messages per Custom Error
error_messages = {
    CustomErrors.TX_SIZE_ERROR: "\tTransactionSizeError: Cannot perform operation due to transaction size limit! "
                                "Consider enabling multiple transactions.",
    CustomErrors.BC_NOT_FOUND_ERROR: "\tBlockchainNotFoundError: The specified Blockchain has not been found.",
    CustomErrors.TX_NOT_FOUND_ERROR: "\tTransactionNotFoundError: The specified Transaction does not exist. "
                                     "Verify your Transaction Hash.",
    CustomErrors.INVALID_PASSWORD_ERROR: "\tInvalidPasswordError: Data encryption has failed. Verify your credentials.",
    CustomErrors.GENERIC_ERROR: "\tCustomGenericError: Oops, something went wrong! If this behaviour persists, "
                                "please contact Bifröst support staff. "
}


# Define Error Classes
# source for default msg: https://stackoverflow.com/a/56967197
class TransactionSizeError(Exception):
    def __init__(self, msg=error_messages[CustomErrors.TX_SIZE_ERROR], *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class TransactionNotFoundError(Exception):
    def __init__(self, msg=error_messages[CustomErrors.TX_NOT_FOUND_ERROR], *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class BlockchainNotFoundError(Exception):
    def __init__(self, msg=error_messages[CustomErrors.BC_NOT_FOUND_ERROR], *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class InvalidPasswordError(Exception):
    def __init__(self, msg=error_messages[CustomErrors.INVALID_PASSWORD_ERROR], *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class CustomGenericError(Exception):
    def __init__(self, msg=error_messages[CustomErrors.GENERIC_ERROR], *args, **kwargs):
        super().__init__(msg, *args, **kwargs)
