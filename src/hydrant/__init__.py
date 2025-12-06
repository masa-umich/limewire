import click
from nicegui import ui

from limewire.util import SocketAddress

from .hydrant import Hydrant


@click.command(context_settings={"help_option_names": ["--help", "-h"]})
@click.argument("fc_address", type=SocketAddress())
def main(fc_address: tuple[str, int]):
    print("! HYDRANT RUNNING !")

    hydrant = Hydrant(fc_address)

    ui.run(hydrant.main_page, show=False, reload=False)


if __name__ == "__main__":
    main()
