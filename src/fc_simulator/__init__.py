import asyncio
import click

from limewire.util import SocketAddress

from .fc_simulator import FCSimulator
from . import errors


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("fc_address", type=SocketAddress())
@click.option(
    "-r",
    "--runtime",
    type=float,
    default=10,
    help="Amount of time to generate telemetry packets per client (sec).",
)
def main(fc_address: tuple[str, int], runtime: float):
    """Run the FC simulator."""

    try:
        fc_simulator = FCSimulator(*fc_address, runtime)
        asyncio.run(fc_simulator.run())
    except KeyboardInterrupt:
        print("\nCtrl+C received.")
        exit(0)
