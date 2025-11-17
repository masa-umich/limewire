import logging
import sys


def print_limewire_error(err: Exception) -> None:
    """Print a formatted error and exit(1)."""
    logger = logging.getLogger("limewire")
    logger.error(f"[limewire] Error: {err}")
    sys.exit(1)
