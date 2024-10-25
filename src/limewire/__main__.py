import asyncio
import sys

from limewire import handle_telemetry_data


def main():
    """Run Limewire."""
    try:
        asyncio.run(handle_telemetry_data())
    except KeyboardInterrupt:
        print("Ctrl+C recieved.")
        sys.exit(0)


if __name__ == "__main__":
    main()
