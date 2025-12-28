import os
import pathlib

import click
from nicegui import app, ui

from limewire.util import SocketAddress

from .hydrant import Hydrant


@click.command(context_settings={"help_option_names": ["--help", "-h"]})
@click.argument(
    "fc_address", type=SocketAddress(), default="141.212.192.170:5000"
)
@click.option(
    "--log-table",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path),
)
def main(fc_address: tuple[str, int], log_table: pathlib.Path):
    print("! HYDRANT RUNNING !")

    script_dir = os.path.dirname(os.path.abspath(__file__))

    app.add_static_file(
        url_path="/favicon.ico",
        local_file=os.path.join(script_dir, "resources/favicon.ico"),
    )
    app.add_static_file(
        url_path="/lebron.png",
        local_file=os.path.join(script_dir, "resources/lebron.png"),
    )
    app.add_static_file(
        url_path="/lebron_shoot.jpg",
        local_file=os.path.join(script_dir, "resources/lebron_shoot.jpg"),
    )

    hydrant = Hydrant(fc_address, log_table)

    ui.run(hydrant.main_page, show=False, reload=False, favicon="favicon.ico")


if __name__ == "__main__":
    main()
