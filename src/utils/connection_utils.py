import socket
import sys
from asyncio import AbstractEventLoop

from lmp.framer import TelemetryProtocol


async def setup_udp_listener(loop: AbstractEventLoop, port: int):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if sys.platform != "win32":
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("0.0.0.0", port))

    res = await loop.create_datagram_endpoint(TelemetryProtocol, sock=sock)
    return res
