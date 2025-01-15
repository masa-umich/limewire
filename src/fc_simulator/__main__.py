import asyncio
import os
import sys

from dotenv import load_dotenv

from fc_simulator import run_server
from fc_simulator.errors import print_fc_error


def main():
    """Run the FC simulator."""
    # Load IP and port from environment variables
    load_dotenv()
    LIMELIGHT_FC_IP = os.getenv("LIMELIGHT_FC_IP")
    LIMELIGHT_FC_PORT = os.getenv("LIMELIGHT_FC_PORT")

    # Prefer IP address and port from command line variables
    if len(sys.argv) >= 2:
        LIMELIGHT_FC_IP, LIMELIGHT_FC_PORT = sys.argv[1].split(":", maxsplit=2)

    if LIMELIGHT_FC_IP is None:
        print_fc_error(ValueError("No IP address specified."))
    if LIMELIGHT_FC_PORT is None:
        print_fc_error(ValueError("No port specified."))

    try:
        LIMELIGHT_FC_PORT = int(LIMELIGHT_FC_PORT)
    except (ValueError, TypeError):
        print_fc_error(ValueError(f"Invalid port {LIMELIGHT_FC_PORT}."))

    run_time = 10
    if len(sys.argv) >= 3:
        try:
            run_time = float(sys.argv[2])
        except (ValueError, TypeError):
            print_fc_error(ValueError(f"Invalid run_time {sys.argv[2]}"))

    try:
        asyncio.run(run_server(LIMELIGHT_FC_IP, LIMELIGHT_FC_PORT, run_time))
    except KeyboardInterrupt:
        print("\nCtrl+C received.")
        exit(0)


if __name__ == "__main__":
    main()
