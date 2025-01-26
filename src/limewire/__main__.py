import asyncio
import sys

import click

import limewire
from limewire.errors import print_limewire_error
from limewire.util import SocketAddress


@click.command(context_settings={"help_option_names": ["--help", "-h"]})
@click.argument("fc_address", type=SocketAddress())
@click.option(
    "--enable-logging",
    default=False,
    is_flag=True,
    help="Log latency data to a JSON file.",
)
def main(fc_address: tuple[str, int], enable_logging: bool):
    """Run Limewire."""

    try:
        asyncio.run(limewire.run(*fc_address, enable_logging))  # pyright: ignore[reportPrivateLocalImportUsage]
    except KeyboardInterrupt:
        print("\nCtrl+C recieved.")
        sys.exit(0)
    except ConnectionRefusedError as err:
        print_limewire_error(err)


if __name__ == "__main__":
    main()
