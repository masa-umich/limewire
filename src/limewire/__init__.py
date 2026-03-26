import asyncio

import click

from utils import SocketAddress

from .limewire import Limewire
from .logging import set_up_logging


@click.command(context_settings={"help_option_names": ["--help", "-h"]})
@click.argument(
    "fc_address", type=SocketAddress(), default="141.212.192.170:5000"
)
@click.option("--debug", is_flag=True)
@click.option("--overwrite-timestamps", is_flag=True)
@click.option("--periodic-sync", is_flag=True)
def main(
    fc_address: tuple[str, int],
    debug: bool,
    overwrite_timestamps: bool,
    periodic_sync: bool,
):
    """Run Limewire."""

    set_up_logging(debug)

    limewire = Limewire(fc_address, overwrite_timestamps, periodic_sync)

    try:
        asyncio.run(limewire.start())
    except KeyboardInterrupt:
        pass
