import asyncio

import click

from limewire import Limewire
from limewire.errors import print_limewire_error
from limewire.logging import set_up_logging
from limewire.util import SocketAddress


@click.command(context_settings={"help_option_names": ["--help", "-h"]})
@click.argument(
    "fc_address", type=SocketAddress(), default="141.212.192.170:5000"
)
@click.option("--debug", is_flag=True)
def main(fc_address: tuple[str, int], debug: bool):
    """Run Limewire."""

    set_up_logging(debug)

    limewire = Limewire()

    try:
        asyncio.run(limewire.start(fc_address))  # pyright: ignore[reportPrivateLocalImportUsage]
    except KeyboardInterrupt:
        pass
    except ConnectionRefusedError as err:
        print_limewire_error(err)


if __name__ == "__main__":
    main()
