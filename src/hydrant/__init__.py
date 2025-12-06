import click
from nicegui import ui

from hydrant.logging import set_up_logging
from limewire.util import SocketAddress

from .hydrant import Hydrant


@click.command(context_settings={"help_option_names": ["--help", "-h"]})
@click.argument("fc_address", type=SocketAddress())
@click.option("--debug")
def main(fc_address: tuple[str, int], debug: bool):
    set_up_logging(debug)

    hydrant = Hydrant(fc_address)

    ui.run(hydrant.main_page, show=False, reload=False)


if __name__ == "__main__":
    main()
