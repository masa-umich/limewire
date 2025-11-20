import asyncio

import click

from limewire.util import SocketAddress

from .proxy import Proxy


@click.command(help="Connect to the flight computer and record timestamps")
@click.argument("endpoint", required=False)
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
def main(endpoint: str | None, host: str, port: int, out_path: str) -> None:
    proxy = Proxy(host=host, port=port, out_path=out_path, out_format="csv")
    try:
        asyncio.run(proxy.start())
    except KeyboardInterrupt:
        # Graceful shutdown on Ctrl+C
        pass
