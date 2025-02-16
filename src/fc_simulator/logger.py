import json
from datetime import datetime

import synnax as sy

from limewire.synnax_util import synnax_init


def log_latency_data(start: sy.TimeStamp, timestamp_channels: list[str]):
    """Write a log containing message latency information to a JSON file.

    Latency is calculated by keeping track of when each message is sent
    in the simulator, then comparing it with the timestamp in Synnax
    when that data was written.

    Args:
        start: The sy.TimeStamp when the FC simulator started sending
            values to Limewire.
        timestamp_channels: A list of names of timestamp channels written
            to during the current FC simulator run.
    """

    client, _ = synnax_init()

    end = sy.TimeStamp.now()
    print(f"Range start = {start}, Range end = {end}")
    synnax_range = client.ranges.create(
        name=f"Limewire Range {datetime.now()}",
        time_range=sy.TimeRange(
            start=start,
            end=end,
        ),
    )

    # Calculate latencies from difference between synnax write and send times
    latency_log: dict[str, list[float]] = {}
    for timestamp in timestamp_channels:
        write_time_channel_name = (
            f"{timestamp.replace('_timestamp', '')}_limewire_write_time"
        )
        print(write_time_channel_name)
        write_times = synnax_range[write_time_channel_name]
        send_times = synnax_range[timestamp]
        raw_latency = list(write_times - send_times)
        latency_log[timestamp] = [float(l) / 10**9 for l in raw_latency]

    # Write log to file
    filename = f"limewire_latency_{datetime.now()}.json"
    filename = filename.replace(" ", "_").replace(":", "-")
    with open(filename, "w") as f:
        json.dump(latency_log, f, indent=4)
