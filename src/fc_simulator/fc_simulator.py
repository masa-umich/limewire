import asyncio
from functools import partial

import synnax as sy

from packets import TelemetryMessage, TelemetryValue


async def handle_client(
    _reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    run_time: int,
) -> None:
    addr: str = writer.get_extra_info("peername")
    print(f"Connected to {addr}.")

    start_time = asyncio.get_event_loop().time()

    FC_NUM_CHANNELS = 47
    values_sent = 0
    while True:
        values = [TelemetryValue(i) for i in range(FC_NUM_CHANNELS)]
        packet = TelemetryMessage(
            board_id=0, timestamp=sy.TimeStamp.now(), values=values
        )

        writer.write(bytes(packet))
        await writer.drain()
        values_sent += len(packet.values)

        if asyncio.get_event_loop().time() - start_time > run_time:
            break

    print(f"Connection with {addr} closed.")
    writer.close()
    await writer.wait_closed()
    print(
        f"Sent {values_sent} telemetry values in {
            run_time} sec ({values_sent/run_time:.2f} values/sec)"
    )


async def run_server(ip_addr: str, port: int, run_time: int) -> None:
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
