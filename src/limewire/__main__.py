import asyncio
import logging
import logging.handlers
import os

import click
from platformdirs import user_log_dir

from limewire import Limewire
from limewire.errors import print_limewire_error
from limewire.util import SocketAddress


class ErrorCodeFormatter(logging.Formatter):
    def format(self, record):
        # Ensure error_code exists
        if not hasattr(record, "error_code"):
            record.error_code = "Unknown"

        return super().format(record)


def setup_logging(verbosity: str):
    # TODO: confirm this
    log_dir = user_log_dir("limewire", "masa")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "limewire.log")

    logging_level = (
        logging.DEBUG
        if verbosity == "debug"
        else logging.ERROR
        if verbosity == "sparse"
        else logging.INFO
    )

    log_format = "%(asctime)s.%(msecs)03d %(error_code)s %(message)s"
    log_dateFmt = "%Y-%m-%dT%H:%M:%S"
    formatter = ErrorCodeFormatter(log_format, datefmt=log_dateFmt)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    # TODO: Change address once port is chosen
    syslog_handler = logging.handlers.SysLogHandler(address=("localhost", 1234))
    syslog_handler.setFormatter(formatter)

    logging.basicConfig(
        level=logging_level,
        handlers=[file_handler, stream_handler, syslog_handler],
    )


@click.command(context_settings={"help_option_names": ["--help", "-h"]})
@click.argument("fc_address", type=SocketAddress())
# debug, normal, sparse
@click.argument("verbosity", type=str, required=False)
def main(fc_address: tuple[str, int], verbosity: str = "normal"):
    """Run Limewire."""

    setup_logging(verbosity)

    limewire = Limewire()

    try:
        asyncio.run(limewire.start(fc_address))  # pyright: ignore[reportPrivateLocalImportUsage]
    except KeyboardInterrupt:
        pass
    except ConnectionRefusedError as err:
        print_limewire_error(err)


if __name__ == "__main__":
    main()
