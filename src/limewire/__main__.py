import asyncio
import os
import sys

from dotenv import load_dotenv

from limewire import handle_telemetry_data
from limewire.errors import print_limewire_error


def main():
    """Run Limewire."""

    # Load IP and port from environment variables
    load_dotenv()
    LIMELIGHT_FC_IP = os.getenv("LIMELIGHT_FC_IP")
    LIMELIGHT_FC_PORT = os.getenv("LIMELIGHT_FC_PORT")

    # Prefer IP address and port from command line variables
    if len(sys.argv) == 2:
        LIMELIGHT_FC_IP, LIMELIGHT_FC_PORT = sys.argv[1].split(":", maxsplit=2)

    if LIMELIGHT_FC_IP is None:
        print_limewire_error(ValueError("No IP address specified."))
    if LIMELIGHT_FC_PORT is None:
        print_limewire_error(ValueError("No port specified."))

    try:
        LIMELIGHT_FC_PORT = int(LIMELIGHT_FC_PORT)
    except (ValueError, TypeError):
        print_limewire_error(ValueError(f"Invalid port {LIMELIGHT_FC_PORT}."))

    try:
        asyncio.run(handle_telemetry_data(LIMELIGHT_FC_IP, LIMELIGHT_FC_PORT))
    except KeyboardInterrupt:
        print("Ctrl+C recieved.")
        sys.exit(0)
    except ConnectionRefusedError as err:
        print_limewire_error(err)


if __name__ == "__main__":
    main()
