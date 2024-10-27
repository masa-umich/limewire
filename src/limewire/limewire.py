import asyncio

from packets import TelemetryPacket, TelemetryValue


async def deserialize_packet(bytes_recv: bytes) -> int:
    """Convert bytes to TelemetryValues and return number of values processed.

    Args:
        bytes_recv: The raw telemetry bytes.

    Returns:
        The number of telemetry values processed.
    """
    packet = TelemetryPacket(bytes_recv=bytes_recv)
    print(f"Received: {packet}")
    return len(packet.values)


async def handle_telemetry_data(ip_addr: str, port: int) -> None:
    """Read incoming telemetry data and print data to STDOUT.

    Args:
        ip_addr: The flight computer's IP address.
        port: The port to connect to the flight computer to.
    """
    try:
        reader, writer = await asyncio.open_connection(ip_addr, port)
    except ConnectionRefusedError:
        # Give a more descriptive error message
        raise ConnectionRefusedError(
            f"Unable to connect to flight computer at {ip_addr}:{port}."
        )

    print(f"Connected to {writer.get_extra_info("peername")}.")

    start_time = asyncio.get_event_loop().time()

    packets_received = 0
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

                values_bytes = await reader.readexactly(
                    num_values * TelemetryValue.SIZE_BYTES
                )
                if not values_bytes:
                    break

                values_received += await deserialize_packet(values_bytes)
                packets_received += 1
            case _:
                raise ValueError("Invalid Limestone packet header.")

    print("Closing connection... ", end="")
    writer.close()
    await writer.wait_closed()
    print("Done.")

    elapsed_time = asyncio.get_event_loop().time() - start_time
    print(
        f"Received {packets_received} packets in {elapsed_time:.2f} sec ({
            packets_received/elapsed_time:.2f} packets/sec, {values_received / elapsed_time} values/sec)"
    )
