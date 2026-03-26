import pathlib

import click

from lmp.util import Board

from .parser import Parser


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument(
    "log_file",
    type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path),
)
def main(log_file: pathlib.Path):
    """Parse a flash dump file"""
    parser = Parser(log_file)
    for board in Board:
        parser.parse(board)
