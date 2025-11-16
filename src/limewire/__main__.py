import asyncio

import click

from limewire import Limewire
from limewire.errors import print_limewire_error
from limewire.logging import setup_logging
from limewire.util import SocketAddress


@click.command(context_settings={"help_option_names": ["--help", "-h"]})
@click.argument("fc_address", type=SocketAddress())
# debug, normal, sparse
@click.argument("verbosity", type=str, required=False)
def main(fc_address: tuple[str, int], verbosity: str = "normal"):
    """Run Limewire."""

    setup_logging(verbosity)

    limewire = Limewire()

    try:
        asyncio.run(limewire.start(fc_address))  # pyright: ignore[reportPrivateLocalImportUsage]
    except KeyboardInterrupt:
        pass
    except ConnectionRefusedError as err:
        print_limewire_error(err)


if __name__ == "__main__":
    main()
