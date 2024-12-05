import os

import synnax as sy
from dotenv import load_dotenv


def synnax_init() -> (sy.Synnax, list[str]):
    """Load channels.txt and create all channels.

    Returns:
        A tuple (client, index_channels, data_channels) where
        client is the Synnax Client object, index_channels is
        a list of all the timestamp channels, and data_channels
        contains a list of all the data channels read in from
        channels.txt.
    """

    load_dotenv()

    client = sy.Synnax(
        host=os.environ["SYNNAX_HOST"],
        port=int(os.environ["SYNNAX_PORT"]),
        username=os.environ["SYNNAX_USERNAME"],
        password=os.environ["SYNNAX_PASSWORD"],
        secure=True,
    )

    with open("data/channels.txt") as f:
        channel_names = f.readlines()
        # Remove leading comment
        channel_names = channel_names[1:]

    boards = ["fc", "bb1", "bb2", "bb3"]
    # Create index channels
    index_channels = []
    for board in boards:
        index_channels.append(
            sy.Channel(
                name=f"{board}_timestamp",
                data_type=sy.DataType.TIMESTAMP,
                is_index=True,
            )
        )

    # Create data channels
    data_channels = []
    for name in channel_names:
        index_channel = index_channels[boards.indexof(name.split("_")[0])]
        data_channels.append(
            sy.Channel(
                name=name,
                data_type=sy.DataType.UINT8
                if "state" in name or "cmd" in name
                else sy.DataType.FLOAT32,
                index=index_channel.key,
            )
        )

    client.channels.create(index_channels, retrieve_if_name_exists=True)
    client.channels.create(data_channels, retrieve_if_name_exists=True)

    return client, index_channels, data_channels


def get_index_name(channel: str) -> str:
    """Return the index channel name associated with the given channel."""
    return f"{channel.split("_")[0]}_timestamp"
