"""
Utility classes and functions for both Limewire and the FC simulator.
"""

import json
import os
import re
import sys
from enum import Enum
from pathlib import Path
from typing import override

import click
import synnax as sy
from dotenv import load_dotenv
from loguru import logger


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


def synnax_init() -> tuple[sy.Synnax, dict[str, list[str]]]:
    """Load channels.json and retrieve channels from Synnax.

    Returns:
        A tuple (client, channels) where client is the Synnax
        Client object and channels is a dictionary mapping timestamp channel
        names to lists of data channels associated with that timestamp channel.
    """

    load_dotenv()

    # TODO: Add log statement when using default credentials
    SYNNAX_HOST = os.getenv("SYNNAX_HOST") or "localhost"
    SYNNAX_PORT = int(os.getenv("SYNNAX_PORT") or 9090)
    SYNNAX_USERNAME = os.getenv("SYNNAX_USERNAME") or "synnax"
    SYNNAX_PASSWORD = os.getenv("SYNNAX_PASSWORD") or "seldon"
    SYNNAX_SECURE = False  # bool(os.getenv("SYNNAX_SECURE") or False)
    LIMEWIRE_DEV_SYNNAX = (
        False  # bool(os.getenv("LIMEWIRE_DEV_SYNNAX") or False)
    )

    try:
        client = sy.Synnax(
            host=SYNNAX_HOST,
            port=SYNNAX_PORT,
            username=SYNNAX_USERNAME,
            password=SYNNAX_PASSWORD,
            secure=SYNNAX_SECURE,
        )
    except Exception as err:
        # Catching on Exception is bad practice, but unavoidable here because
        # freighter doesn't expose freighter.exceptions.Unreachable. We print
        # the specific error type below for debugging purposes.
        logger.error("Failed to connect to Synnax (Is Synnax running?)")
        logger.error(
            f"Env Vars Dump: SYNNAX_HOST: {SYNNAX_HOST}, SYNNAX_PORT: {SYNNAX_PORT}, SYNNAX_USERNAME: {SYNNAX_USERNAME}, SYNNAX_PASSWORD: {SYNNAX_PASSWORD}, SYNNAX_SECURE: {SYNNAX_SECURE}, LIMEWIRE_DEV_SYNNAX: {LIMEWIRE_DEV_SYNNAX}"
        )
        logger.error(f"{type(err).__module__}.{type(err).__qualname__}: {err}")
        sys.exit(1)

    logger.info(
        f"Connected to Synnax at {SYNNAX_HOST}:{SYNNAX_PORT} (LIMEWIRE_DEV_SYNNAX={LIMEWIRE_DEV_SYNNAX})"
    )

    channels_file = Path(__file__).parent / "data" / "channels.json"
    with channels_file.open() as f:
        channels: dict[str, list[str]] = json.load(f)

    # If LIMEWIRE_DEV_SYNNAX is set, then Limewire will only create the
    # fc_timestamp channels in order to stay under the 50-channel limit
    # imposed by Synnax.
    if LIMEWIRE_DEV_SYNNAX:
        channels = {"fc_timestamp": channels["fc_timestamp"]}

    index_channels: list[sy.Channel] = []
    for index_name in channels.keys():
        index_channels.append(
            sy.Channel(
                name=index_name,
                data_type=sy.DataType.TIMESTAMP,
                is_index=True,
            )
        )

    client.channels.create(index_channels, retrieve_if_name_exists=True)

    data_channels: list[sy.Channel] = []
    for index_name, channel_names in channels.items():
        index_channel = client.channels.retrieve(index_name)
        for name in channel_names:
            data_channels.append(
                sy.Channel(
                    name=name,
                    data_type=get_data_type(name),
                    index=index_channel.key,
                )
            )

    client.channels.create(data_channels, retrieve_if_name_exists=True)

    return client, channels


def is_valve_command_channel(channel_name: str) -> bool:
    name_split = channel_name.split("_")

    if len(name_split) != 3:
        return False

    return name_split[1] == "vlv"


def is_valve_state_channel(channel_name: str) -> bool:
    name_split = channel_name.split("_")

    if len(name_split) != 3:
        return False

    return name_split[1] == "state"


def get_data_type(channel_name: str) -> sy.DataType:
    """Return the DataType associated with the channel."""
    if "limewire" in channel_name:
        return sy.DataType.TIMESTAMP
    if is_valve_command_channel(channel_name) or is_valve_state_channel(
        channel_name
    ):
        return sy.DataType.UINT8
    return sy.DataType.FLOAT32


def get_write_time_channel_name(ch_name: str) -> str:
    """Return this timestamp channel's limewire write time channel."""
    return ch_name.replace("timestamp", "limewire_write_time")
