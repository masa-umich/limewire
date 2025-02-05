import asyncio
import statistics
import time

import synnax as sy

from .logger import Logger
from .messages import TelemetryMessage, TelemetryValue
from .synnax_util import synnax_init


async def read_telemetry_data(
    reader: asyncio.StreamReader,
    queue: asyncio.Queue[tuple[bytes, float]],
) -> int:
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
                board_id = await reader.read(1)
                if not board_id:
                    break

                FC_NUM_VALUES = 47
                BB_NUM_VALUES = 52
                if int.from_bytes(board_id) == 0:
                    num_values = FC_NUM_VALUES
                else:
                    num_values = BB_NUM_VALUES

                data_bytes = await reader.readexactly(
                    8 + num_values * TelemetryValue.SIZE_BYTES
                )
                if not data_bytes:
                    break

                await queue.put(
                    (board_id + data_bytes, asyncio.get_event_loop().time())
                )
                values_received += num_values
            case _:
                raise ValueError(
                    f"Invalid Limestone packet header 0x{header:X}."
                )

    return values_received


async def write_data_to_synnax(
    queue: asyncio.Queue[tuple[bytes, float]],
    writer: sy.Writer,
    channels: dict[str, list[str]],
    logger: Logger,
) -> None:
    """Write telemetry data from queue to Synnax.

    This function currently prints the data to STDOUT instead
    of writing to Synnax as a stand-in.

    Args:
        queue: The queue containing telemetry values.
        writer: The Synnax writer.
        channels: A dictionary mapping index channel names to data
            channel names.
        logger: The logger object to store message processing latency
            data.
    """
    while True:
        # Parse telemetry data bytes
        data_bytes, enter_time = await queue.get()
        try:
            message = TelemetryMessage(bytes_recv=data_bytes)
            data_to_write = {
                channel: value.data
                for channel, value in zip(
                    channels[message.get_index_channel()], message.values
                )
            }
            data_to_write[message.get_index_channel()] = message.timestamp

            writer.write(data_to_write)  # pyright: ignore[reportArgumentType]
            writer.commit()

            # Track processing time
            logger.log(
                "telemetry",
                {"latency": asyncio.get_event_loop().time() - enter_time},
            )
        except ValueError as err:
            print(f"{err}")
        finally:
            queue.task_done()


async def run(ip_addr: str, port: int, enable_logging: bool):
    """Open the TCP connection and the Synnax connection and run Limewire.

    Args:
        ip_addr: The flight computer's IP address.
        port: The port to connect to the flight computer to.
        enable_logging: Whether or not to write latency data to a file.
    """

    # Initialize Synnax client
    print("Initializing Synnax writer...", end="")
    client, channels = synnax_init()
    synnax_writer = client.open_writer(
        start=sy.TimeStamp.now(),
        channels=list(channels.keys())
        + [ch for chs in channels.values() for ch in chs],
        enable_auto_commit=True,
    )

    # This helps mitigate commit time mismatches on different systems
    time.sleep(1)
    print("Done.")

    # Initialize TCP connection to flight computer
    try:
        tcp_reader, tcp_writer = await asyncio.open_connection(ip_addr, port)
    except ConnectionRefusedError:
        # Give a more descriptive error message
        raise ConnectionRefusedError(
            f"Unable to connect to flight computer at {ip_addr}:{port}."
        )
    print(f"Connected to {tcp_writer.get_extra_info("peername")}.")
    start_time = asyncio.get_event_loop().time()

    # Set up read and write tasks
    queue: asyncio.Queue[tuple[bytes, float]] = asyncio.Queue()
    logger = Logger()
    receive_task = asyncio.create_task(read_telemetry_data(tcp_reader, queue))
    write_task = asyncio.create_task(
        write_data_to_synnax(queue, synnax_writer, channels, logger)
    )
    values_received = await receive_task

    await queue.join()
    write_task.cancel()
    synnax_writer.close()
    write_time = asyncio.get_event_loop().time() - start_time

    print("Closing connection... ", end="")
    tcp_writer.close()
    await tcp_writer.wait_closed()
    print("Done.")

    if values_received == 0:
        print("Unable to receive telemetry data from flight computer!")
        return

    # Print statistics
    print(
        f"Processed {values_received} values in {write_time:.2f} sec ({
            values_received/write_time:.2f} values/sec)"
    )

    telemetry_message_latencies: list[float] = logger.get_data(  # pyright: ignore[reportAssignmentType]
        "telemetry", "latency"
    )
    mean_ms = statistics.mean(telemetry_message_latencies) * 1000
    jitter_ms = max(
        mean_ms - min(telemetry_message_latencies) * 1000,
        max(telemetry_message_latencies) * 1000 - mean_ms,
    )
    print(f"Message Latency: {mean_ms:.2f} ± {jitter_ms:.2f} ms")
    print(
        f"Stdev: {statistics.stdev(telemetry_message_latencies) * 1000:.2f} ms"
    )

    if enable_logging:
        print("Writing log...", end="")
        logger.write_log()
        print("Done.")
