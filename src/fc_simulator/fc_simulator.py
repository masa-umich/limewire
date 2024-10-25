import asyncio
import sys

from packets import TelemetryPacket, TelemetryValue


async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    addr = writer.get_extra_info("peername")
    print(f"Connected to {addr}.")

    start_time = asyncio.get_event_loop().time()
    timeout_sec = 10

    packets_sent = 0
    while True:
        values = [TelemetryValue(i, i * 2, i * 3) for i in range(3)]
        packet = TelemetryPacket(values=values)

        writer.write(bytes(packet))
        await writer.drain()
        packets_sent += 1

        if asyncio.get_event_loop().time() - start_time > timeout_sec:
            break

    print(f"Connection with {addr} closed.")
    writer.close()
    await writer.wait_closed()
    print(
        f"Sent {packets_sent} packets in {
            timeout_sec} sec ({packets_sent/timeout_sec:.2f} packets/sec)"
    )


async def run_server():
    server = await asyncio.start_server(handle_client, "127.0.0.1", 8888)

    addr = server.sockets[0].getsockname()
    print(f"Serving on {addr}.")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("Ctrl+C received.")
        exit(0)
