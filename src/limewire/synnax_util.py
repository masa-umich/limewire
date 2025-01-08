import json
import os
from pathlib import Path

import synnax as sy
from dotenv import load_dotenv


def synnax_init() -> tuple[sy.Synnax, dict[str, list[str]]]:
    """Load channels.json and retrieve channels from Synnax.

    Returns:
        A tuple (client, channels) where client is the Synnax
        Client object and channels is a dictionary mapping timestamp channel
        names to lists of data channels associated with that timestamp channel.
    """

    load_dotenv()

    client = sy.Synnax(
        host=os.environ["SYNNAX_HOST"],
        port=int(os.environ["SYNNAX_PORT"]),
        username=os.environ["SYNNAX_USERNAME"],
        password=os.environ["SYNNAX_PASSWORD"],
        secure=bool(os.environ["SYNNAX_SECURE"]),
    )

    channels_file = Path(__file__).parent / "data" / "channels.json"
    with channels_file.open() as f:
        channels: dict[str, list[str]] = json.load(f)

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
                    data_type=sy.DataType.UINT8
                    if "state" in name or "cmd" in name
                    else sy.DataType.FLOAT32,
                    index=index_channel.key,
                    rate=sy.Rate(50),
                )
            )

    client.channels.create(data_channels, retrieve_if_name_exists=True)

    return client, channels


def get_index_name(channel: str) -> str:
    """Return the index channel name associated with the given channel."""
    return f"{channel.split("_")[0]}_timestamp"
