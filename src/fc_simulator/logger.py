import json
from datetime import datetime

import synnax as sy

from limewire.synnax_util import synnax_init


def log_latency_data(msg_send_times: dict[str, list[sy.TimeStamp]]):
    """Write a log containing message latency information to a JSON file.

    Latency is calculated by keeping track of when each message is sent
    in the simulator, then comparing it with the timestamp in Synnax
    when that data was written.

    Args:
        msg_send_times: A dictionary where keys are names of Synnax
            timestamp channels and values are lists of sy.TimeStamp
            objects representing when each packet was sent.
    """

    client, _ = synnax_init()

    # Ensure that we only get values within the test window by creating
    # a range that spans the first "sent" timestamp to right now.
    start_timestamp = None
    for send_times in msg_send_times.values():
        for send_time in send_times:
            if start_timestamp is None or send_time < start_timestamp:
                start_timestamp = send_time

    if start_timestamp is None:
        raise ValueError("msg_send_times is empty")

    test_range = client.ranges.create(
        name=f"Limewire Range {datetime.now()}",
        time_range=sy.TimeRange(
            start=start_timestamp,
            end=sy.TimeStamp.now(),
        ),
    )

    # Calculate latencies from difference between synnax write and send times
    latency_log: dict[str, list[float]] = {}
    for timestamp_channel, send_times in msg_send_times.items():
        channel = test_range[timestamp_channel]
        if len(send_times) != len(channel):
            raise ValueError(
                f"mismatched number of latency values (sent {len(send_times)}, synnax has {len(channel)})"
            )

        # This line relies on the fact that channel (which is a
        # sy.ScopedChannel) acts as an np.ndarray, so we can subtract
        # arrays elementwise.
        latency_log[timestamp_channel] = channel - send_times  # pyright: ignore[reportOperatorIssue]

    # Write log to file
    filename = f"limewire_latency_{datetime.now()}.json"
    filename = filename.replace(" ", "_").replace(":", "-")
    with open(filename, "w") as f:
        json.dump(latency_log, f, indent=4)
