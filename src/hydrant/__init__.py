import click
from nicegui import ui

from limewire.util import SocketAddress

import pathlib

from .hydrant import Hydrant


@click.command(context_settings={"help_option_names": ["--help", "-h"]})
@click.argument("fc_address", type=SocketAddress())
@click.option("--log-table", default=None, type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path))
def main(fc_address: tuple[str, int], log_table: pathlib.Path):
    print("! HYDRANT RUNNING !")

    hydrant = Hydrant(fc_address, log_table)

    ui.run(hydrant.main_page, show=False, reload=False)


if __name__ == "__main__":
    main()
