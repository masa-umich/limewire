import asyncio
import random
from functools import partial

import synnax as sy

from limewire.messages import BoardID, TelemetryMessage


async def handle_client(
    _reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    run_time: float,
) -> None:
    addr: str = writer.get_extra_info("peername")
    print(f"Connected to {addr}.")

    start_time = asyncio.get_running_loop().time()
    synnax_start_time = None

    FC_NUM_CHANNELS = 47
    values_sent = 0
    while True:
        loop_start_time = asyncio.get_running_loop().time()

        values = [i * random.uniform(0, 1) for i in range(FC_NUM_CHANNELS)]

        timestamp = sy.TimeStamp.now()
        if synnax_start_time is None:
            synnax_start_time = timestamp

        msg = TelemetryMessage.from_data(BoardID.FC, timestamp, values)
        msg_bytes = bytes(msg)

        writer.write(len(msg_bytes).to_bytes(1, byteorder="big") + msg_bytes)
        await writer.drain()

        values_sent += len(msg.values)

        if asyncio.get_running_loop().time() - start_time > run_time:
            break

        # Add delay to send packets at 50Hz
        DATA_RATE = 50
        loop_elapsed_time = asyncio.get_running_loop().time() - loop_start_time
        await asyncio.sleep(max(0, 1 / DATA_RATE - loop_elapsed_time))

    print(f"Connection with {addr} closed.")
    writer.close()
    await writer.wait_closed()
    print(
        f"Sent {values_sent} telemetry values in {run_time} sec ({values_sent / run_time:.2f} values/sec)"
    )


async def run_server(ip_addr: str, port: int, run_time: float) -> None:
    """Run the FC simulator.

    Args:
        ip_addr: The IP address with which to start the TCP server.
        port: The port with which to start the server.
    """
    # We have to pass a partial function because asyncio.start_server()
    # expects a function with only two arguments. functools.partial()
    # "fills in" the run_time argument for us and returns a new function
    # with only the two expected arguments.
    server = await asyncio.start_server(
        partial(handle_client, run_time=run_time),
        ip_addr,
        port,
    )

    addr: str = server.sockets[0].getsockname()
    print(f"Serving on {addr}.")

    async with server:
        await server.serve_forever()
