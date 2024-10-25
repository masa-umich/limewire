import asyncio
import sys

from packets import TelemetryPacket, TelemetryValue


async def deserialize_packet(bytes_recv: bytes):
    packet = TelemetryPacket(bytes_recv=bytes_recv)
    print(f"Received: {packet}")
    return


async def handle_telemetry_data():
    reader, writer = await asyncio.open_connection("127.0.0.1", 8888)

    print(f"Connected to {writer.get_extra_info("peername")}.")

    start_time = asyncio.get_event_loop().time()

    telemetry_packets_received = 0
    bytes_received = 0
    while True:
        header_byte = await reader.read(1)
        if not header_byte:
            break
        bytes_received += 1

        header = int.from_bytes(header_byte)
        match header:
            case 0x01:
                num_values = await reader.read(1)
                if not num_values:
                    break
                num_values = int.from_bytes(num_values)
                bytes_received += 1

                values_bytes = await reader.readexactly(
                    num_values * TelemetryValue.SIZE_BYTES
                )
                if not values_bytes:
                    break
                bytes_received += num_values * TelemetryValue.SIZE_BYTES

                await deserialize_packet(values_bytes)
                telemetry_packets_received += 1
            case _:
                raise ValueError("Invalid Limestone packet header.")

    print("Closing connection... ", end="")
    writer.close()
    await writer.wait_closed()
    print("Done.")

    elapsed_time = asyncio.get_event_loop().time() - start_time
    print(
        f"Received {telemetry_packets_received} packets in {elapsed_time:.2f} sec ({
            telemetry_packets_received/elapsed_time:.2f} packets/sec, {bytes_received * 8 / elapsed_time / 1000:.2f} kbps)"
    )


if __name__ == "__main__":
    message = "Hello, world!"
    if len(sys.argv) >= 2:
        message = sys.argv[1]

    try:
        asyncio.run(handle_telemetry_data())
    except KeyboardInterrupt:
        print("Ctrl+C recieved.")
        sys.exit(0)
