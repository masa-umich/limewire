import asyncio

import click

from .limewire import Limewire
from .logging import set_up_logging
from .util import SocketAddress


@click.command(context_settings={"help_option_names": ["--help", "-h"]})
@click.argument(
    "fc_address", type=SocketAddress(), default="141.212.192.170:5000"
)
# @click.argument(
#     "gs_address",
#     type=SocketAddress(),
#     default="141.212.192.175:5000",  # TODO: Set this radio address correctly
# )
@click.option("--debug", is_flag=True)
@click.option("--overwrite-timestamps", is_flag=True)
def main(
    fc_address: tuple[str, int],
    # gs_address: tuple[str, int],
    debug: bool,
    overwrite_timestamps: bool,
):
    """Run Limewire."""

    set_up_logging(debug)

    limewire = Limewire(fc_address, overwrite_timestamps)

    try:
        asyncio.run(limewire.start())  # pyright: ignore[reportPrivateLocalImportUsage]
    except KeyboardInterrupt:
        pass
