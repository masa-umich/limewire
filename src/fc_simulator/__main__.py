import asyncio

import click

from fc_simulator import FCSimulator
from limewire.util import SocketAddress


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
        fc_simulator = FCSimulator()
        asyncio.run(fc_simulator.run(*fc_address, runtime))
    except KeyboardInterrupt:
        print("\nCtrl+C received.")
        exit(0)


if __name__ == "__main__":
    main()
