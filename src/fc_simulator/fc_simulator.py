import asyncio
import random
import socket
import time
from functools import partial

import synnax as sy

from limewire.messages import (
    Board,
    TelemetryMessage,
    ValveCommandMessage,
    ValveStateMessage,
    DeviceCommandMessage,
)
from limewire.messages.util import DeviceCommand


class FCSimulator:
    """The flight computer simulator."""

    UDP_PORT: int = 1234

    def __init__(self, ip_addr: str, tcp_port: int, run_time: float):
        self.ip_addr = ip_addr
        self.tcp_port = tcp_port
        self.run_time = run_time

        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    async def generate_telemetry_data(
        self, addr: str, writer: asyncio.StreamWriter, run_time: float
    ) -> None:
        """Send randomly generated telemetry data to Limewire."""

        start_time = asyncio.get_running_loop().time()

        boards = [
            Board.FC,
            Board.BB1,
            Board.BB2,
            Board.BB3,
            Board.FR,
        ]

        values_sent = 0
        while True:
            loop_start_time = asyncio.get_running_loop().time()

            for board in boards:
                values = [
                    i * random.uniform(0, 1) for i in range(board.num_values)
                ]

                timestamp = sy.TimeStamp.now()
                msg = TelemetryMessage(board, timestamp, values)
                msg_bytes = bytes(msg)

                writer.write(len(msg_bytes).to_bytes(1) + msg_bytes)
                await writer.drain()

                values_sent += len(msg.values)

            if asyncio.get_running_loop().time() - start_time > run_time:
                break

            # Add delay to send packets at 50Hz
            DATA_RATE = 50
            loop_elapsed_time = (
                asyncio.get_running_loop().time() - loop_start_time
            )
            await asyncio.sleep(max(0, 1 / DATA_RATE - loop_elapsed_time))

        actual_run_time = asyncio.get_running_loop().time() - start_time

        print(
            f"Sent {values_sent} telemetry values in {actual_run_time:.2f} sec ({values_sent / actual_run_time:.2f} values/sec)"
        )

    async def handle_commands(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        while True:
            msg_length = await reader.read(1)
            if not msg_length:
                break

            msg_length = int.from_bytes(msg_length)
            msg_bytes = await reader.readexactly(msg_length)
            if not msg_bytes:
                break

            msg_id = int.from_bytes(msg_bytes[0:1])
            match msg_id:
                case ValveCommandMessage.MSG_ID:
                    cmd_msg = ValveCommandMessage.from_bytes(msg_bytes)
                    state_msg = ValveStateMessage(
                        cmd_msg.valve, cmd_msg.state, int(sy.TimeStamp.now())
                    )
                    state_msg_bytes = bytes(state_msg)
                    writer.write(
                        len(state_msg_bytes).to_bytes(1) + state_msg_bytes
                    )
                    await writer.drain()
                case DeviceCommandMessage.MSG_ID:
                    command = DeviceCommandMessage.from_bytes(msg_bytes)
                    match command.command:
                        case DeviceCommand.CLEAR_FLASH:
                            print("Clearing flash")
                        case _:
                            print("Not implemented!")

    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        run_time: float,
    ) -> None:
        addr: str = writer.get_extra_info("peername")
        print(f"Connected to {addr}.")

        telemetry_task = asyncio.create_task(
            self.generate_telemetry_data(addr, writer, run_time)
        )
        valve_task = asyncio.create_task(self.handle_commands(reader, writer))

        await telemetry_task
        await valve_task

        writer.close()
        await writer.wait_closed()
        print(f"Connection with {addr} closed.")

    async def run(self) -> None:
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
            partial(self.handle_client, run_time=self.run_time),
            self.ip_addr,
            self.tcp_port,
        )

        addr: str = server.sockets[0].getsockname()
        print(f"Serving on {addr}.")

        async with server:
            await server.serve_forever()

        while True:
            self.udp_socket.sendto(
                b"Hello, world!\r\n", ("127.0.0.1", self.UDP_PORT)
            )
