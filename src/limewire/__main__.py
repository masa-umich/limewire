import asyncio
import sys

from limewire import handle_telemetry_data


def main():
    """Run Limewire."""
    try:
        asyncio.run(handle_telemetry_data("127.0.0.1", 8888))
    except KeyboardInterrupt:
        print("Ctrl+C recieved.")
        sys.exit(0)
    except ConnectionRefusedError as err:
        print(str(err))
        sys.exit(1)


if __name__ == "__main__":
    main()
