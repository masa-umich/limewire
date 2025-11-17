import matplotlib.pyplot as plt
import seaborn as sns

from ..utils.util import synnax_init


def get_latency_data(range_name: str, timestamp_channels: list[str]) -> dict:
    """Return a log containing message latency information to a JSON file.

    Latency is calculated by keeping track of when each message is sent
    in the simulator, then comparing it with the timestamp in Synnax
    when that data was written.

    Args:
        range_name: The name of the range from which to create the latency
            log. This range should have been created in the Synnax console
            before running this function.
        timestamp_channels: A list of names of timestamp channels written
            to during the current FC simulator run.
    """

    client, _ = synnax_init()
    synnax_range = client.ranges.retrieve(name=range_name)

    # Calculate latencies from difference between synnax write and send times
    latency_log: dict[str, list[float]] = {}
    for timestamp in timestamp_channels:
        write_time_channel_name = (
            f"{timestamp.replace('_timestamp', '')}_limewire_write_time"
        )
        write_times = synnax_range[write_time_channel_name]
        send_times = synnax_range[timestamp]
        raw_latency = list(write_times - send_times)  # pyright: ignore[reportOperatorIssue]
        latency_log[timestamp] = [float(l) / 10**9 for l in raw_latency]

    return latency_log


def plot_latency_data(latency_log: dict[str, list[float]]):
    """Create a latency histogram for each index channel."""
    for index_channel, latency_data in latency_log.items():
        sns.histplot(data=latency_data)
        plt.show()
