import click
from nicegui import ui, app

from limewire.util import SocketAddress

from .hydrant import Hydrant

import os
from pathlib import Path


@click.command(context_settings={"help_option_names": ["--help", "-h"]})
@click.argument(
    "fc_address", type=SocketAddress(), default="141.212.192.170:5000"
)
def main(fc_address: tuple[str, int]):
    print("! HYDRANT RUNNING !")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))

    app.add_static_file(url_path='/favicon.ico', local_file=os.path.join(script_dir, 'resources/favicon.ico'))
    app.add_static_file(url_path='/lebron.png', local_file=os.path.join(script_dir, 'resources/lebron.png'))
    app.add_static_file(url_path='/lebron_shoot.jpg', local_file=os.path.join(script_dir, 'resources/lebron_shoot.jpg'))
    
    hydrant = Hydrant(fc_address)

    ui.run(hydrant.main_page, show=False, reload=False, favicon="favicon.ico")

if __name__ == "__main__":
    main()
