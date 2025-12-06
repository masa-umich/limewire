import asyncio
import platform
from asyncio.streams import StreamReader, StreamWriter
from contextlib import asynccontextmanager

import asyncudp
import synnax as sy
from loguru import logger

from lmp import (
    HeartbeatMessage,
    LMPFramer,
    LMPMessage,
    TelemetryFramer,
    TelemetryMessage,
    Valve,
    ValveCommandMessage,
    ValveStateMessage,
)
from lmp.framer import FramingError

from .ntp_sync import send_ntp_sync
from .util import get_write_time_channel_name, synnax_init


WINERROR_SEMAPHORE_TIMEOUT = 121


class Limewire:
    """A class to manage Limewire's resources."""

    def __init__(self) -> None:
        logger.info("Limewire started.")

        self.synnax_client, self.channels = synnax_init()
        self.synnax_writer = None
        self.queue: asyncio.Queue[LMPMessage] = asyncio.Queue()

    async def start(self, fc_addr: tuple[str, int]) -> None:
        """Open a connection to the flight computer and start Limewire.

        Args:
            fc_addr: A tuple (ip_addr, port) indicating the flight
                computer's TCP socket address.
        """

        # We need to define an asynccontextmanager to ensure that shutdown
        # code runs after the task is canceled because of e.g. Ctrl+C
        @asynccontextmanager
        async def lifespan():
            try:
                yield
            finally:
                logger.info("Limewire stopped.")
                await self.stop()

        async with lifespan():
            self.synnax_writer = await self._open_synnax_writer(
                sy.TimeStamp.now()
            )
            await asyncio.sleep(0.5)

            telemetry_socket = await asyncudp.create_socket(
                local_addr=("0.0.0.0", 6767)
            )
            self.telemetry_framer = TelemetryFramer(telemetry_socket)
            logger.info("Listening for telemetry on UDP port 6767")

            self.connected = False
            while True:
                try:
                    logger.info(
                        f"Connecting to flight computer at {fc_addr[0]}:{fc_addr[1]}..."
                    )

                    async with asyncio.timeout(1):
                        tcp_reader, tcp_writer = await self._connect_fc(
                            *fc_addr
                        )
                        self.lmp_framer = LMPFramer(tcp_reader, tcp_writer)
                        self.connected = True
                except TimeoutError:
                    logger.warning("Connection attempt timed out.")
                    continue
                except ConnectionRefusedError:
                    logger.warning("Connection refused.")
                    continue
                except OSError as err:
                    if (
                        platform.system() == "Windows"
                        and getattr(err, "winerr", None)
                        == WINERROR_SEMAPHORE_TIMEOUT
                    ):
                        logger.warning(
                            f"Connection attempt timed out (Windows OSError: {str(err)})."
                        )
                        continue
                    else:
                        raise err

                peername = tcp_writer.get_extra_info("peername")
                logger.info(
                    f"Connected to flight computer at {peername[0]}:{peername[1]}."
                )

                # Set up async tasks
                self.start_time = asyncio.get_event_loop().time()
                # Track whether you need to reconnect
                reconnect = False
                try:
                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self._fc_tcp_read())
                        tg.create_task(self._fc_telemetry_listen())
                        tg.create_task(self._synnax_write())
                        tg.create_task(self._relay_valve_cmds())
                        tg.create_task(self._send_heartbeat())
                except* ConnectionResetError:
                    logger.error("Connection to flight computer lost.")
                    reconnect = True
                except* Exception as eg:
                    logger.error(
                        f"Tasks failed with {len(eg.exceptions)} error(s)"
                    )
                    for exc in eg.exceptions:
                        logger.exception(
                            "Exception raised with type %s: %s", type(exc), exc
                        )
                if reconnect:
                    continue
                else:
                    break

    async def stop(self):
        """Run shutdown code."""

        await self.lmp_framer.close()

        if self.synnax_writer is not None:
            try:
                self.synnax_writer.close()
            except sy.ValidationError:
                logger.warning(
                    "Ignoring Synnax writer internal validation error(s)."
                )

        logger.info("=" * 60)

    async def _send_heartbeat(self):
        HEARTBEAT_INTERVAL = 1
        while True:
            try:
                await self.lmp_framer.send_message(HeartbeatMessage())
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                logger.debug(f"Queue size: {self.queue.qsize()}")
            except ConnectionResetError as err:
                raise err
                # print(err)

    async def _connect_fc(
        self, ip_addr: str, port: int
    ) -> tuple[StreamReader, StreamWriter]:
        """Establish the TCP connection to the flight computer.

        Args:
            ip_addr: The IP address portion of the flight computer socket
                address.
            port: The port at which the flight computer is listening for
                connections.
        Returns:
            A tuple (reader, writer) containing the TCP reader and writer
            objects, respectively.
        Raises:
            ConnectionRefusedError: Limewire was unable to connect to the
                flight computer at the given socket address.
        """
        try:
            return await asyncio.open_connection(ip_addr, port)
        except ConnectionRefusedError:
            # Give a more descriptive error message
            raise ConnectionRefusedError(
                f"Unable to connect to flight computer at {ip_addr}:{port}."
            )

    async def _fc_tcp_read(self):
        """Handle incoming data from the TCP connection.

        Returns:
            The number of telemetry values processed.
        """
        while True:
            try:
                message = await self.lmp_framer.receive_message()
            except (FramingError, ValueError) as err:
                logger.error(str(err))
                logger.opt(exception=err).debug("Traceback: ", exc_info=True)
                continue

            if message is None:
                break

            if type(message) is ValveStateMessage:
                await self.queue.put(message)
            else:
                pass
                # TODO: log warning

    async def _fc_telemetry_listen(self):
        """Listen for telemetry messages."""
        while True:
            message = await self.telemetry_framer.receive_message()
            await self.queue.put(message)

    async def _synnax_write(self) -> None:
        """Write telemetry data and valve state data to Synnax."""
        while True:
            message = await self.queue.get()

            if not isinstance(message, TelemetryMessage) and not isinstance(
                message, ValveStateMessage
            ):
                logger.warning(
                    f"Invalid message type '{str(type(message))}' in queue."
                )
                self.queue.task_done()
                continue

            frame = self._build_synnax_frame(message)
            if frame is None:
                self.queue.task_done()
                continue

            if self.synnax_writer is None:
                self.synnax_writer = await self._open_synnax_writer(
                    message.timestamp
                )

            try:
                self.synnax_writer.write(frame)
            except sy.ValidationError as err:
                logger.warning(
                    f"Synnax validation error '{str(err)}', skipping frame"
                )
                # logger.info("Sending NTP sync...")
                # TODO: Move this to Hydrant
                # send_ntp_sync()

            self.queue.task_done()

    def _build_synnax_frame(
        self, msg: TelemetryMessage | ValveStateMessage
    ) -> dict | None:
        if isinstance(msg, TelemetryMessage):
            try:
                frame = self._build_telemetry_frame(msg)
            except KeyError as err:
                logger.error(str(err), extra={"error_code": "0006"})
                return None
        else:
            frame = self._build_valve_state_frame(msg)

        return frame

    def _build_telemetry_frame(self, msg: TelemetryMessage) -> dict:
        """Construct a frame to write to Synnax from a telemetry message.

        Raises:
            KeyError: Index channel for given message is not loaded.
        """

        # Check if index channel is loaded
        if msg.index_channel not in self.channels:
            raise KeyError(
                f"Channel {msg.index_channel} not active! Is LIMEWIRE_DEV_SYNNAX enabled?"
            )

        data_channels = self.channels[msg.index_channel].copy()
        limewire_write_time_channel = get_write_time_channel_name(
            msg.index_channel
        )
        data_channels.remove(limewire_write_time_channel)
        frame = {
            channel: value for channel, value in zip(data_channels, msg.values)
        }
        frame[msg.index_channel] = msg.timestamp
        frame[limewire_write_time_channel] = sy.TimeStamp.now()

        return frame

    def _build_valve_state_frame(self, msg: ValveStateMessage) -> dict:
        """Construct a frame to write to Synnax from a valve state message."""
        frame = {}
        frame[msg.valve.state_channel_index] = msg.timestamp
        frame[msg.valve.state_channel] = int(msg.state)
        limewire_write_time_channel = get_write_time_channel_name(
            msg.valve.state_channel_index
        )
        frame[limewire_write_time_channel] = sy.TimeStamp.now()
        return frame

    async def _open_synnax_writer(self, timestamp: int) -> sy.Writer:
        """Return an initialized Synnax writer using the given timestamp."""

        # Create a list of all channels
        writer_channels = []
        for index_channel, data_channels in self.channels.items():
            writer_channels.append(index_channel)
            for ch in data_channels:
                writer_channels.append(ch)

        writer = self.synnax_client.open_writer(
            start=timestamp,
            channels=writer_channels,
            enable_auto_commit=True,
            authorities=0,  # Limewire should never control command channels,
        )

        return writer

    async def _relay_valve_cmds(self):
        """Relay valve commands from Synnax to the flight computer."""

        # Create a list of all valve command channels
        data_channels: list[sy.Channel] = []
        for data_channel_names in self.channels.values():
            for channel_name in data_channel_names:
                data_channels.append(
                    self.synnax_client.channels.retrieve(channel_name)  # pyright: ignore[reportArgumentType]
                )

        cmd_channels = []
        for channel in data_channels:
            if (
                channel.data_type == sy.DataType.UINT8
                and "state" not in channel.name
            ):
                cmd_channels.append(channel)

        async with await self.synnax_client.open_async_streamer(
            cmd_channels
        ) as streamer:
            async for frame in streamer:
                logger.debug("Received frame from streamer.")
                for channel, series in frame.items():
                    valve = Valve.from_channel_name(channel)  # pyright: ignore[reportArgumentType]
                    # For now, let's assume that if multiple values are in the
                    # frame, we only care about the most recent one
                    logger.debug("Sending ValveCommandMessage.")
                    msg = ValveCommandMessage(valve, bool(series[-1]))
                    await self.lmp_framer.send_message(msg)
