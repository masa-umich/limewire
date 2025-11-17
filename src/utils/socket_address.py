import re
from typing import override

import click


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
