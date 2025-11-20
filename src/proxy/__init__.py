import asyncio

import click

from limewire.util import SocketAddress

from .proxy import Proxy


@click.command(help="Connect to the flight computer and record timestamps")
@click.argument(
    "fc_address",
    type=SocketAddress(),
    default="141.212.192.170:5000",
)
@click.option(
    "--out",
    "out_path",
    type=str,
    default="proxy_log.csv",
    show_default=True,
    help="Output file path (CSV)",
)
def main(fc_address: tuple[str, int], out_path: str) -> None:
    proxy = Proxy(out_path=out_path)

    try:
        asyncio.run(proxy.start(fc_address))
    except KeyboardInterrupt:
        # Graceful shutdown on Ctrl+C
        pass
