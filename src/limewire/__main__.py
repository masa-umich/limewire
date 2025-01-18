import asyncio
import re
import sys
from typing import override

import click

import limewire
from limewire.errors import print_limewire_error


class SocketAddress(click.ParamType):
    """A class to enable click to parse socket addresses with nice error messages."""

    name: str = "address:port"
    _pattern: re.Pattern[str] = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}:\d{1,5}$")

    @override
    def convert(
        self,
        value: str,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> tuple[str, int]:
        """Convert a string to an (ip, port) socket address."""

        if not self._pattern.match(value):
            self.fail(
                "Address must be of the form [ip-address]:[port]",
                param,
                ctx,
            )

        ip, port = value.rsplit(":", 1)
        port = int(port)
        if not (0 <= port <= 65535):
            self.fail("Port must be between 0 and 65535", param, ctx)

        return ip, port


@click.command()
@click.argument("fc_address", type=SocketAddress())
def main(fc_address: tuple[str, int]):
    """Run Limewire."""

    try:
        asyncio.run(limewire.run(*fc_address))  # pyright: ignore[reportPrivateLocalImportUsage]
    except KeyboardInterrupt:
        print("\nCtrl+C recieved.")
        sys.exit(0)
    except ConnectionRefusedError as err:
        print_limewire_error(err)


if __name__ == "__main__":
    main()
