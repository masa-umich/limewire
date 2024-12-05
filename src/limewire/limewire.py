import asyncio
import statistics

import synnax as sy

from packets import TelemetryMessage, TelemetryValue

from .synnax_util import synnax_init


async def read_telemetry_data(
    reader: asyncio.StreamReader,
    queue: asyncio.Queue,
) -> tuple[int, int]:
    """Read incoming telemetry data and push to queue.

    Args:
        ip_addr: The flight computer's IP address.
        port: The port to connect to the flight computer to.
    """

    values_received = 0
    while True:
        header_byte = await reader.read(1)
        if not header_byte:
            break

        header = int.from_bytes(header_byte)
        match header:
            case 0x01:
                num_values = await reader.read(1)
                if not num_values:
                    break
                num_values = int.from_bytes(num_values)

                data_bytes = await reader.readexactly(
                    num_values * TelemetryValue.SIZE_BYTES + 8
                )
                if not data_bytes:
                    break

                await queue.put((data_bytes, asyncio.get_event_loop().time()))
                values_received += num_values
            case _:
                raise ValueError(
                    f"Invalid Limestone packet header 0x{header:X}."
                )

    return values_received


async def write_data_to_synnax(
    queue: asyncio.Queue,
    message_processing_times: list,
    client: sy.Synnax,
    data_channels: list[str],
) -> None:
    """Write telemetry data from queue to Synnax.

    This function currently prints the data to STDOUT instead
    of writing to Synnax as a stand-in.

    Args:
        queue: The queue containing telemetry values.
        message_processing_times: A list containing the time it took
            to process each message.
        client: The Synnax client.
        data_channels: A list of all data channels, with indices
            corresponding to the channel ID in the Limelight packet
            structure.
    """
    while True:
        data_bytes, enter_time = await queue.get()
        packet = TelemetryMessage(bytes_recv=data_bytes)
        message_processing_times.append(
            asyncio.get_event_loop().time() - enter_time
        )
        print(f"Received: {packet}")
        queue.task_done()


async def run(ip_addr: str, port: int):
    """Open the TCP connection and the Synnax connection and run Limewire.

    Args:
        ip_addr: The flight computer's IP address.
        port: The port to connect to the flight computer to.
    """

    client, data_channels = None, None

    try:
        reader, writer = await asyncio.open_connection(ip_addr, port)
    except ConnectionRefusedError:
        # Give a more descriptive error message
        raise ConnectionRefusedError(
            f"Unable to connect to flight computer at {ip_addr}:{port}."
        )
    print(f"Connected to {writer.get_extra_info("peername")}.")
    start_time = asyncio.get_event_loop().time()

    queue = asyncio.Queue()
    message_processing_times = []

    receive_task = asyncio.create_task(read_telemetry_data(reader, queue))
    write_task = asyncio.create_task(
        write_data_to_synnax(
            queue, message_processing_times, client, data_channels
        )
    )
    values_received = await receive_task

    await queue.join()
    write_task.cancel()

    write_time = asyncio.get_event_loop().time() - start_time

    print("Closing connection... ", end="")
    writer.close()
    await writer.wait_closed()
    print("Done.")

    print(
        f"Processed {values_received} values in {write_time:.2f} sec ({
            values_received/write_time:.2f} values/sec)"
    )

    mean_ms = statistics.mean(message_processing_times) * 1000
    jitter_ms = max(
        mean_ms - min(message_processing_times) * 1000,
        max(message_processing_times) * 1000 - mean_ms,
    )
    print(f"\nMessage Latency: {mean_ms:.2f} ± {jitter_ms:.2f} ms")
    print(f"Stdev: {statistics.stdev(message_processing_times) * 1000} ms")
