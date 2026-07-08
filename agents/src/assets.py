import logging
import sys


# Helpers
def get_logger() -> logging.Logger:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


# Errors
class NoCSRFException(Exception):
    pass


class NoRedirectURLException(Exception):
    pass


class NoCodeInURLException(Exception):
    pass


class TokenExchangeFailedException(Exception):
    pass
