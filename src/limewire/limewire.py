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
from .util import (
    get_write_time_channel_name,
    is_valve_command_channel,
    synnax_init,
)

WINERROR_SEMAPHORE_TIMEOUT = 121


class Limewire:
    """A class to manage Limewire's resources."""

    synnax_client: sy.Synnax
    channels: dict[str, list[str]]
    synnax_writer: sy.Writer | None
    lmp_framer: LMPFramer | None
    telemetry_framer: TelemetryFramer | None
    queue: asyncio.Queue[tuple[LMPMessage, float]]
    overwrite_timestamps: bool
    connected: bool

    def __init__(self, overwrite_timestamps: bool = False) -> None:
        logger.info(
            f"Limewire started (overwrite_timestamps={overwrite_timestamps})."
        )

        self.synnax_client, self.channels = synnax_init()
        self.synnax_writer = None
        self.lmp_framer = None
        self.telemetry_framer = None
        self.queue = asyncio.Queue()
        self.overwrite_timestamps = overwrite_timestamps
        self.connected = False

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
            self.synnax_writer = self._open_synnax_writer(sy.TimeStamp.now())
            await asyncio.sleep(0.5)

            telemetry_socket = await asyncudp.create_socket(
                local_addr=("0.0.0.0", 6767)
            )
            self.telemetry_framer = TelemetryFramer(telemetry_socket)
            logger.info("Listening for telemetry on UDP port 6767")

            self.connected = False
            while True:
                # Send NTP sync before connecting to ensure correct
                # telemetry message timestamps.
                send_ntp_sync(logger)

                try:
                    logger.info(
                        f"Connecting to flight computer at {fc_addr[0]}:{fc_addr[1]}..."
                    )

                    async with asyncio.timeout(5):
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
                    await asyncio.sleep(1)
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

                peername = tcp_writer.get_extra_info("peername")  # pyright: ignore[reportAny]
                logger.info(
                    f"Connected to flight computer at {peername[0]}:{peername[1]}."
                )

                # Track whether you need to reconnect
                reconnect = False
                try:
                    # Set up async tasks
                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self._fc_tcp_read())
                        tg.create_task(self._fc_telemetry_listen())
                        tg.create_task(self._synnax_write())
                        tg.create_task(self._relay_valve_cmds())
                        tg.create_task(self._send_heartbeat())
                except* ConnectionResetError:
                    logger.error("Connection to flight computer lost.")
                    reconnect = True
                except* OSError as eg:
                    for err in eg.exceptions:
                        if (
                            platform.system() == "Windows"
                            and getattr(err, "winerr", None)
                            == WINERROR_SEMAPHORE_TIMEOUT
                        ):
                            logger.warning(
                                f"Connection attempt timed out (Windows OSError: {str(err)})."
                            )
                            reconnect = True
                    else:
                        raise eg
                except* Exception as eg:
                    logger.error(
                        f"Tasks failed with {len(eg.exceptions)} error(s)"
                    )
                    for exc in eg.exceptions:
                        logger.opt(exception=exc).error("Traceback: ")
                if reconnect:
                    continue
                else:
                    break

    async def stop(self):
        """Run shutdown code."""

        if self.lmp_framer is not None:
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
            await asyncio.sleep(HEARTBEAT_INTERVAL)

            logger.debug(f"Queue size: {self.queue.qsize()}")

            if self.lmp_framer is None:
                continue

            try:
                await self.lmp_framer.send_message(HeartbeatMessage())
            except ConnectionResetError as err:
                raise err

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
            if self.lmp_framer is None:
                # Yield control back to runtime
                await asyncio.sleep(0)
                continue

            try:
                framer_return = await self.lmp_framer.receive_message()
            except (FramingError, ValueError) as err:
                logger.error(str(err))
                logger.opt(exception=err).debug("Traceback: ", exc_info=True)
                continue

            if framer_return is None:
                break

            message, recv_time = framer_return

            if type(message) is ValveStateMessage:
                await self.queue.put((message, recv_time))
            else:
                pass
                # TODO: log warning

    async def _fc_telemetry_listen(self):
        """Listen for telemetry messages."""
        while True:
            if self.telemetry_framer is None:
                # Yield control back to runtime
                await asyncio.sleep(0)
                continue

            message, recv_time = await self.telemetry_framer.receive_message()

            if self.overwrite_timestamps:
                message.timestamp = sy.TimeStamp.now()

            await self.queue.put((message, recv_time))

    async def _synnax_write(self) -> None:
        """Write telemetry data and valve state data to Synnax."""
        while True:
            message, recv_time = await self.queue.get()

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

            latency_channel: str
            if isinstance(message, TelemetryMessage):
                latency_channel = "limewire_telemetry_latency"
            else:
                latency_channel = "limewire_valve_state_latency"

            self._synnax_write_frame(
                frame, message.timestamp, recv_time, latency_channel
            )

            self.queue.task_done()

    def _synnax_write_frame(
        self,
        frame: dict[str, float],
        timestamp: int,
        latency_start_time: float,
        latency_channel: str,
    ):
        """Write a frame to Synnax including latency information."""
        if self.synnax_writer is None:
            try:
                self.synnax_writer = self._open_synnax_writer(timestamp)
            except sy.ValidationError as err:
                logger.warning(
                    f"Synnax validation error '{str(err)}', skipping frame"
                )
                send_ntp_sync(logger)
                return

        frame[f"{latency_channel}_timestamp"] = sy.TimeStamp.now()
        frame[latency_channel] = (
            asyncio.get_running_loop().time() - latency_start_time
        )

        try:
            self.synnax_writer.write(frame)  # pyright: ignore[reportArgumentType]
        except sy.ValidationError as err:
            logger.warning(
                f"Synnax validation error '{str(err)}', skipping frame"
            )

            try:
                self.synnax_writer.close()
            except sy.ValidationError:
                # Why oh why must you be this way Synnax :(
                #
                # (For context, if a ValidationError occurs, the
                # error state doesn't get cleared from the writer, so
                # when we try to close the writer it will re-raise the
                # error which is why we have to handle it a second time
                # here.)
                pass

            # Writer will get re-initialzed next time its needed
            self.synnax_writer = None

            send_ntp_sync(logger)

    def _build_synnax_frame(
        self, msg: TelemetryMessage | ValveStateMessage
    ) -> dict[str, float] | None:
        if isinstance(msg, TelemetryMessage):
            try:
                frame = self._build_telemetry_frame(msg)
            except KeyError as err:
                logger.error(str(err))
                return None
        else:
            frame = self._build_valve_state_frame(msg)

        return frame

    def _build_telemetry_frame(self, msg: TelemetryMessage) -> dict[str, float]:
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

    def _build_valve_state_frame(
        self, msg: ValveStateMessage
    ) -> dict[str, float]:
        """Construct a frame to write to Synnax from a valve state message."""
        frame: dict[str, float] = {}
        frame[msg.valve.state_channel_index] = msg.timestamp
        frame[msg.valve.state_channel] = int(msg.state)
        limewire_write_time_channel = get_write_time_channel_name(
            msg.valve.state_channel_index
        )
        frame[limewire_write_time_channel] = sy.TimeStamp.now()
        return frame

    def _open_synnax_writer(self, timestamp: int) -> sy.Writer:
        """Return an initialized Synnax writer using the given timestamp."""

        # Create a list of all channels
        writer_channels: list[str] = []
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
        cmd_channels: list[str] = []
        for data_channel_names in self.channels.values():
            for channel_name in data_channel_names:
                if is_valve_command_channel(channel_name):
                    cmd_channels.append(channel_name)

        async with await self.synnax_client.open_async_streamer(
            cmd_channels
        ) as streamer:
            recv_time = asyncio.get_running_loop().time()

            async for frame in streamer:
                for channel, series in frame.items():
                    valve = Valve.from_channel_name(channel)  # pyright: ignore[reportArgumentType]
                    # For now, let's assume that if multiple values are in the
                    # frame, we only care about the most recent one
                    msg = ValveCommandMessage(valve, bool(series[-1]))  # pyright: ignore[reportUnknownArgumentType]

                    if self.lmp_framer is None:
                        continue

                    await self.lmp_framer.send_message(msg)

                    # Write latency data to Synnax
                    self._synnax_write_frame(
                        {},
                        sy.TimeStamp.now(),
                        recv_time,
                        "limewire_valve_command_latency",
                    )
