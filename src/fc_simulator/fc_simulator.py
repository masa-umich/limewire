import asyncio
import random
import socket
import sys
from functools import partial

import synnax as sy

from limewire.util import FlightPhase, SwitchNetwork
from lmp import (
    Board,
    DeviceCommandAckMessage,
    DeviceCommandMessage,
    HandoffMessage,
    HeartbeatMessage,
    TelemetryFramer,
    TelemetryMessage,
    ValveCommandMessage,
    ValveStateMessage,
)
from lmp.framer import TelemetryProtocol
from lmp.handoff import ControlSignal
from lmp.util import DeviceCommand


def format_socket_address(addr: tuple[str, int]) -> str:
    """Format of addr: [address, port]"""

    return addr[0] + ":" + str(addr[1])


class FCSimulator:
    """The flight computer simulator."""

    UDP_PORT: int = 1234

    def __init__(
        self,
        fc_addr: tuple[str, int],
        gs_addr: tuple[str, int],
        run_time: float,
    ):
        self.configs = {
            FlightPhase.ETHERNET: fc_addr,
            FlightPhase.RADIO: gs_addr,
        }
        self.config = FlightPhase.ETHERNET
        self.run_time = run_time

        self.log_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.log_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.tcp_aborted = False

    async def generate_telemetry_data(self, run_time: float) -> None:
        """Send randomly generated telemetry data to Limewire."""
        loop = asyncio.get_event_loop()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if sys.platform != "win32":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("0.0.0.0", 0))
        # Connect to broadcast
        sock.connect(("255.255.255.255", 6767))
        (
            _,
            handler,
        ) = await loop.create_datagram_endpoint(TelemetryProtocol, sock=sock)

        self.telemetry_framer = TelemetryFramer(sock=handler)
        print("Sending telemetry at 255.255.255.255:6767")

        start_time = asyncio.get_running_loop().time()

        boards = [
            Board.FC,
            Board.BB1,
            Board.BB2,
            Board.BB3,
            Board.FR,
        ]

        values_sent = 0
        loop_counter = 0
        while True:
            loop_start_time = asyncio.get_running_loop().time()
            for board in boards:
                if board == Board.FR:
                    values = [float("nan") for i in range(board.num_values)]
                else:
                    values = [
                        i * random.uniform(0, 1)
                        for i in range(board.num_values)
                    ]
                # Send a 0-timestamped telemetry message every 100 messages
                if loop_counter % 100 == 0:
                    timestamp = loop_counter
                else:
                    timestamp = sy.TimeStamp.now()

                msg = TelemetryMessage(board, timestamp, values)
                self.telemetry_framer.send_message(msg)

                values_sent += len(msg.values)

            if asyncio.get_running_loop().time() - start_time > run_time:
                break

            # Add delay to send packets at 50Hz
            DATA_RATE = 50
            loop_elapsed_time = (
                asyncio.get_running_loop().time() - loop_start_time
            )
            await asyncio.sleep(max(0, 1 / DATA_RATE - loop_elapsed_time))

            loop_counter += 1

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

            response_msg = await self.handle_message(msg_bytes)
            if not response_msg:
                continue

            if (
                response_msg.MSG_ID == HandoffMessage.MSG_ID
                and type(response_msg) is HandoffMessage
            ):
                # Handoff is happening
                if (
                    response_msg.confirmation_seq
                    != HandoffMessage.DEFAULT_CONFIRMATION_SEQ
                ):
                    continue

                if (
                    self.config == FlightPhase.ETHERNET
                    and response_msg.control_signal == ControlSignal.HANDOFF
                ):
                    self.config = FlightPhase.RADIO
                    raise SwitchNetwork()
                elif (
                    self.config == FlightPhase.RADIO
                    and response_msg.control_signal == ControlSignal.ABORT
                ):
                    self.config = FlightPhase.ETHERNET
                    raise SwitchNetwork()
                else:
                    continue

            response_bytes = bytes(response_msg)
            writer.write(len(response_bytes).to_bytes(1) + response_bytes)
            await writer.drain()

    async def handle_message(
        self, msg_bytes: bytes
    ) -> ValveStateMessage | DeviceCommandAckMessage | HandoffMessage | None:
        """Return the response message associated with the command message.

        Args:
            msg_bytes: The message from which to generate the response. MUST
                be either a ValveCommandMessage or DeviceCommandMessge.

        Raises:
            ValueError: Received a non-command message.
        """
        msg_id = int.from_bytes(msg_bytes[0:1])
        match msg_id:
            case ValveCommandMessage.MSG_ID:
                cmd_msg = ValveCommandMessage.from_bytes(msg_bytes)
                return ValveStateMessage(
                    cmd_msg.valve, cmd_msg.state, int(sy.TimeStamp.now())
                )

            case DeviceCommandMessage.MSG_ID:
                cmd_msg = DeviceCommandMessage.from_bytes(msg_bytes)

                response = DeviceCommandAckMessage(
                    cmd_msg.board, cmd_msg.command
                )

                match cmd_msg.command:
                    case DeviceCommand.FLASH_SPACE:
                        response.response_msg = "67 bytes remaining lmao"
                    case DeviceCommand.FIRMWARE_BUILD_INFO:
                        response.response_msg = (
                            "Build 6.7.67 (commit hash deadbeef)"
                        )
                    case _:
                        pass

                return response
            case HandoffMessage.MSG_ID:
                handoff_msg = HandoffMessage.from_bytes(msg_bytes)
                return handoff_msg
            case HeartbeatMessage.MSG_ID:
                pass
            case _:
                print(f"Received non-command message (header 0x{msg_id:X}).")

    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        run_time: float,
    ) -> None:
        addr = writer.get_extra_info("peername")
        print(f"Connected to {format_socket_address(addr)}.")

        self.tcp_aborted = False

        listen_task = asyncio.create_task(self.handle_commands(reader, writer))

        try:
            await listen_task
        except SwitchNetwork:
            self.switch = True
            self.server.close()

        if not self.tcp_aborted:
            writer.close()
            await writer.wait_closed()
            print(f"Connection with {format_socket_address(addr)} closed.")

    async def run(self) -> None:
        """Run the FC simulator.

        Args:
            ip_addr: The IP address with which to start the TCP server.
            port: The port with which to start the server.
        """

        # Start telemetry task
        telemetry_task = asyncio.create_task(
            self.generate_telemetry_data(self.run_time)
        )

        # We have to pass a partial function because asyncio.start_server()
        # expects a function with only two arguments. functools.partial()
        # "fills in" the run_time argument for us and returns a new function
        # with only the two expected arguments.
        while True:
            self.switch = False
            self.server = await asyncio.start_server(
                partial(self.handle_client, run_time=self.run_time),
                *self.configs[self.config],
            )

            addr = self.server.sockets[0].getsockname()
            print(
                f"Serving on {format_socket_address(addr)}. Config: {self.config.value}"
            )

            try:
                async with self.server:
                    await self.server.serve_forever()

                print("Restarting telemetry task")
                await telemetry_task

                while True:
                    self.log_socket.sendto(
                        b"Hello, world!\r\n", ("127.0.0.1", self.UDP_PORT)
                    )
            except asyncio.CancelledError:
                if self.switch:
                    continue
                else:
                    break
