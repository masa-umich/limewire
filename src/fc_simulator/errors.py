import sys


def print_fc_error(err: Exception) -> None:
    """Print a formatted error and exit(1)."""
    print(f"[fc_simulator] Error: {err}")
    sys.exit(1)
