import asyncio
import sys

import click

from limewire import Limewire
from limewire.errors import print_limewire_error
from limewire.util import SocketAddress


@click.command(context_settings={"help_option_names": ["--help", "-h"]})
@click.argument("fc_address", type=SocketAddress())
def main(fc_address: tuple[str, int]):
    """Run Limewire."""

    try:
        limewire = Limewire()
        asyncio.run(limewire.start(fc_address))  # pyright: ignore[reportPrivateLocalImportUsage]
    except KeyboardInterrupt:
        print("\nCtrl+C recieved.")
        sys.exit(0)
    except ConnectionRefusedError as err:
        print_limewire_error(err)


if __name__ == "__main__":
    main()
