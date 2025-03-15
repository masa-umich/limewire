import asyncio
import time

import synnax as sy

from .messages import TelemetryMessage, TelemetryValue
from .synnax_util import synnax_init


async def read_telemetry_data(
    reader: asyncio.StreamReader,
    queue: asyncio.Queue[bytes],
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

                await queue.put(board_id + data_bytes)
                values_received += num_values
            case _:
                raise ValueError(
                    f"Invalid Limestone packet header 0x{header:X}."
                )

    return values_received


async def write_data_to_synnax(
    queue: asyncio.Queue[bytes],
    client: sy.Synnax,
    channels: dict[str, list[str]],
) -> None:
    """Write telemetry data from queue to Synnax.

    This function currently prints the data to STDOUT instead
    of writing to Synnax as a stand-in.

    Args:
        queue: The queue containing telemetry values.
        client: The Synnax client.
        channels: A dictionary mapping index channel names to data
            channel names.
    """
    # We need to use a global variable here to close the writer after the write
    # task is canceled.
    global synnax_writer
    synnax_writer = None
    while True:
        # Parse telemetry data bytes
        data_bytes = await queue.get()
        try:
            message = TelemetryMessage(bytes_recv=data_bytes)

            # channels contains a "limewire_write_time" channel for each index
            # channel for the purpose of latency logging. This channel's data is
            # intended to be generated by Limewire, and as such is not present
            # in the actual telemetry message.
            data_channels = [
                ch
                for ch in channels[message.get_index_channel()]
                if "limewire" not in ch
            ]
            data_to_write = {
                channel: value.data
                for channel, value in zip(data_channels, message.values)
            }

            # NOTE: This line of code is not robust at all. There are 50 million
            # ways it could fail. (What if channels.json missed the limewire
            # write time channel? What if we add more 'limewire' channels in the
            # future?) But because Python, this is the jank-ness we're using for
            # now.
            limewire_write_time_channel = [
                ch
                for ch in channels[message.get_index_channel()]
                if "limewire" in ch
            ][0]
            data_to_write[message.get_index_channel()] = message.timestamp
            data_to_write[limewire_write_time_channel] = sy.TimeStamp.now()

            if synnax_writer is None:
                writer_channels = list(channels.keys()) + [
                    ch for chs in channels.values() for ch in chs
                ]
                synnax_writer = client.open_writer(
                    start=message.timestamp,
                    channels=writer_channels,
                    enable_auto_commit=True,
                )

            synnax_writer.write(data_to_write)  # pyright: ignore[reportArgumentType]
            synnax_writer.commit()
        except ValueError as err:
            print(f"{err}")
        finally:
            queue.task_done()


async def run(ip_addr: str, port: int):
    """Open the TCP connection and the Synnax connection and run Limewire.

    Args:
        ip_addr: The flight computer's IP address.
        port: The port to connect to the flight computer to.
    """

    # Initialize Synnax client
    print("Initializing Synnax writer...", end="")
    client, channels = synnax_init()

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
    print(f"Connected to {tcp_writer.get_extra_info('peername')}.")
    start_time = asyncio.get_event_loop().time()

    # Set up read and write tasks
    queue: asyncio.Queue[bytes] = asyncio.Queue()
    receive_task = asyncio.create_task(read_telemetry_data(tcp_reader, queue))
    write_task = asyncio.create_task(
        write_data_to_synnax(queue, client, channels)
    )
    values_received = await receive_task

    await queue.join()
    write_task.cancel()
    write_time = asyncio.get_event_loop().time() - start_time

    if synnax_writer is not None:
        synnax_writer.close()

    print("Closing connection... ", end="")
    tcp_writer.close()
    await tcp_writer.wait_closed()
    print("Done.")

    if values_received == 0:
        print("Unable to receive telemetry data from flight computer!")
        return

    # Print statistics
    print(
        f"Processed {values_received} values in {write_time:.2f} sec ({values_received / write_time:.2f} values/sec)"
    )
