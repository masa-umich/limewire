import asyncio
import datetime
import socket
import sys
from enum import Enum

from loguru import logger
from nicegui import Client, ui

from lmp.telemetry import TelemetryMessage
from lmp.util import Board

TELEM_PORT = 6767


class BoardTelemetryUI:
    def __init__(self, channels: list[str], board: Board, columns: int):
        self.channels = channels
        self.board = board
        self.process_message(
            TelemetryMessage(board, None, [None] * board.num_values)
        )
        self.timestamp = None
        with ui.card().classes(
            "w-full h-full bg-gray-900 border border-gray-700 p-6"
        ):
            with ui.row().classes("w-full no-wrap"):
                ui.label(board.pretty_name).classes(
                    "text-xl font-bold text-white mb-2"
                )
                ui.space()
                with ui.row().classes("no-wrap gap-1 items-center"):
                    ui.label("Timestamp: ")
                    ui.label().classes(
                        "border w-[45ch] p-1 pl-2 pr-2 rounded-md"
                    ).bind_text_from(
                        self, "timestamp", backward=process_timestamp
                    )
            with ui.row().classes(
                "mx-auto no-wrap flex items-stretch w-full h-full gap-2"
            ):
                for i in range(columns):
                    with ui.column().classes(
                        "h-full flex-1 basis-auto border-1 p-2 pt-3 pb-3 border-gray-500"
                    ):
                        with ui.grid(columns="auto auto auto").classes(
                            "items-center gap-2 p-0"
                        ):
                            for x in range(
                                -(board.num_values // -columns) * i,
                                min(
                                    -(board.num_values // -columns) * (i + 1),
                                    board.num_values,
                                ),
                            ):
                                if "old" in self.channels[x]:
                                    ui.label(
                                        f"{process_channel_name(self.channels[x])}:"
                                    ).classes("justify-end text-right")
                                    ui.label().classes(
                                        "border w-[9ch] p-1 pl-2 pr-2 rounded-md"
                                    ).bind_text_from(
                                        self,
                                        self.channels[x],
                                        backward=lambda v: (
                                            v.name if v is not None else " - "
                                        ),
                                    )
                                    ui.label("")
                                elif "current" in self.channels[x]:
                                    ui.label(
                                        f"{process_channel_name(self.channels[x])}:"
                                    ).classes("justify-end text-right")
                                    ui.label().classes(
                                        "border w-[9ch] p-1 pl-2 pr-2 rounded-md overflow-hidden"
                                    ).bind_text_from(
                                        self,
                                        self.channels[x],
                                        backward=lambda v: (
                                            f"{(v * 1000):.5g}"
                                            if v is not None
                                            else " - "
                                        ),
                                    )
                                    ui.label(get_channel_unit(self.channels[x]))
                                else:
                                    ui.label(
                                        f"{process_channel_name(self.channels[x])}:"
                                    ).classes("justify-end text-right")
                                    ui.label().classes(
                                        "border w-[9ch] p-1 pl-2 pr-2 rounded-md overflow-hidden"
                                    ).bind_text_from(
                                        self,
                                        self.channels[x],
                                        backward=lambda v: (
                                            f"{v:.5g}"
                                            if v is not None
                                            else " - "
                                        ),
                                    )
                                    ui.label(get_channel_unit(self.channels[x]))

    def process_message(self, msg: TelemetryMessage):
        for x in range(msg.board.num_values):
            if "old" in self.channels[x]:
                setattr(
                    self,
                    self.channels[x],
                    ValveOLD.from_telem(msg.values[x])
                    if msg.values[x] is not None
                    else None,
                )
            else:
                setattr(self, self.channels[x], msg.values[x])
        self.timestamp = (
            datetime.datetime.fromtimestamp(
                msg.timestamp / 1e9, tz=datetime.timezone.utc
            )
            if msg.timestamp is not None
            else None
        )


def process_timestamp(v: datetime.datetime):
    if v is None:
        return " - "
    local_zone = (
        datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
    )
    local_time = v.astimezone(local_zone)
    diff = abs(datetime.datetime.now(datetime.timezone.utc) - v)
    return f"{local_time.strftime('%b %d, %Y %I:%M:%S.')}{(local_time.microsecond // 1000):03d} {local_time.strftime('%p')} {local_time.strftime('%z')} - {(diff.seconds // 3600):02d}:{((diff.seconds % 3600) // 60):02d}:{(diff.seconds % 60):02d}.{int(diff.microseconds // 1e3):03d}"


def process_channel_name(name: str):
    pieces = name.split("_")
    pieces = pieces[1:]
    name = str.join(" ", pieces)
    name = name.replace("pt", "PT")
    name = name.replace("tc", "TC")
    name = name.replace("vlv", "VLV")
    name = name.replace("gps", "GPS")
    name = name.replace("imu", "IMU")
    return name[0].upper() + name[1:] if name != "" else ""


def get_channel_unit(name: str):
    if "pt" in name:
        return "psi"
    elif "tc" in name:
        return "C\u00b0"
    elif "current" in name:
        return "mA"
    elif "bar" in name:
        return "hPa"
    elif "imu" in name:
        if "w" in name:
            return "deg/s"
        else:
            return "m/s\u00b2"
    elif "gps" in name:
        if "alt" in name:
            return "m"  # TODO
        else:
            return "\u00b0"  # TODO
    elif "voltage" in name:
        return "V"
    elif "temp" in name:
        return "C\u00b0"
    else:
        return ""


class ValveOLD(Enum):
    Load = 1
    NoLoad = 0
    En = -1

    @classmethod
    def from_telem(cls, val: float):
        if val == -1.0:
            return ValveOLD.En
        elif val == 0.0:
            return ValveOLD.NoLoad
        elif val == 1.0:
            return ValveOLD.Load
        else:
            raise ValueError(f"OLD value is not 0, 1, or -1: {val}")


class TelemetryListener:
    def __init__(self):
        self.telemetry_UIs: list[tuple[Board, BoardTelemetryUI, Client]] = []
        self.transport = None

    def attach_ui(self, ui: BoardTelemetryUI, board: Board, client: Client):
        self.telemetry_UIs.append((board, ui, client))

    def cleanup(self, client: Client):
        self.telemetry_UIs[:] = [
            x for x in self.telemetry_UIs if x[2] == client
        ]

    async def open_listener(self):
        while True:
            try:
                loop = asyncio.get_event_loop()
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if sys.platform != "win32":
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.bind(("0.0.0.0", TELEM_PORT))
                (
                    self.transport,
                    self.handler,
                ) = await loop.create_datagram_endpoint(
                    self.create_protocol, sock=sock
                )
            except Exception as err:
                logger.error(f"Error opening telemetry listener: {str(err)}")
                await asyncio.sleep(1)
                continue

            try:
                if self.handler is not None:
                    await self.handler.wait_for_close()
            except asyncio.CancelledError:
                logger.warning("Telemetry listener cancelled.")
                break
            except Exception as e:
                logger.error(f"Got exception: {e}")
                continue

    def create_protocol(self):
        return TelemetryProtocol(self)

    def send_to_UIs(self, msg: TelemetryMessage):
        for x in self.telemetry_UIs:
            if x[0] == msg.board:
                x[1].process_message(msg)


class TelemetryProtocol(asyncio.DatagramProtocol):
    def __init__(self, listener):
        super().__init__()
        self.listener: TelemetryListener = listener
        self.open = False

    def connection_made(self, transport):
        self.transport = transport
        self.open = True

    def datagram_received(self, data, addr):
        try:
            telemetry_msg = TelemetryMessage.from_bytes(data[1:])
            self.listener.send_to_UIs(telemetry_msg)
        except Exception as e:
            logger.error("Invalid telemetry message: " + str(e))

    def connection_lost(self, exc):
        self.open = False

    async def wait_for_close(self):
        while self.open:
            await asyncio.sleep(0.5)
