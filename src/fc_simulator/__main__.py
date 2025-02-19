import asyncio

import click

from fc_simulator import run_server
from limewire.util import SocketAddress


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("fc_address", type=SocketAddress())
@click.option(
    "--enable-logging",
    default=False,
    is_flag=True,
    help="Log latency data to a JSON file.",
)
@click.option(
    "-r",
    "--runtime",
    type=float,
    default=10,
    help="Amount of time to generate telemetry packets per client (sec).",
)
def main(fc_address: tuple[str, int], runtime: float, enable_logging: bool):
    """Run the FC simulator."""

    try:
        asyncio.run(run_server(*fc_address, runtime, enable_logging))
    except KeyboardInterrupt:
        print("\nCtrl+C received.")
        exit(0)


if __name__ == "__main__":
    main()
