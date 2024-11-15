import asyncio

from packets import TelemetryPacket, TelemetryValue


async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    addr = writer.get_extra_info("peername")
    print(f"Connected to {addr}.")

    start_time = asyncio.get_event_loop().time()
    timeout_sec = 10

    values_sent = 0
    while True:
        values = [TelemetryValue(i, i * 2, i * 3) for i in range(3)]
        packet = TelemetryPacket(values=values)

        writer.write(bytes(packet))
        await writer.drain()
        values_sent += len(packet.values)

        if asyncio.get_event_loop().time() - start_time > timeout_sec:
            break

    print(f"Connection with {addr} closed.")
    writer.close()
    await writer.wait_closed()
    print(
        f"Sent {values_sent} telemetry values in {
            timeout_sec} sec ({values_sent/timeout_sec:.2f} values/sec)"
    )


async def run_server(ip_addr: str, port: int) -> None:
    server = await asyncio.start_server(handle_client, ip_addr, port)

    addr = server.sockets[0].getsockname()
    print(f"Serving on {addr}.")

    async with server:
        await server.serve_forever()
