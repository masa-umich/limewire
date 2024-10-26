import sys


def print_limewire_error(err: Exception) -> None:
    """Print a formatted error and exit(1)."""
    print(f"[limewire] Error: {err}")
    sys.exit(1)
