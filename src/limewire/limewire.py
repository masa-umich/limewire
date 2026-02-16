import asyncio
import platform
from contextlib import asynccontextmanager

import synnax as sy
from loguru import logger

from lmp import (
    HandoffMessage,
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

from ..utils.connection_utils import setup_udp_listener
from ..utils.limewire_utils import (
    is_valve_command_channel,
    synnax_init,
)
from ..utils.ntp_sync import send_ntp_sync
from ..utils.synnax_framer import SynnaxFramer

WINERROR_SEMAPHORE_TIMEOUT = 121

# Config variables
UDP_PORT = 6767
FC_READ_TIMEOUT = 5.0
FC_CONNECT_TIMEOUT = 5.0
HEARTBEAT_INTERVAL = 1.0


class Limewire:
    """A class to manage Limewire's resources."""

    fc_addr: tuple[str, int]
    gs_addr: tuple[str, int]

    # Synnax
    channels: dict[str, list[str]]
    synnax_client: sy.Synnax
    synnax_writer: sy.Writer | None
    synnax_framer: SynnaxFramer

    # Framers
    lmp_framer: LMPFramer | None
    telemetry_framer: TelemetryFramer | None
    queue: asyncio.Queue[LMPMessage]

    # State booleans
    overwrite_timestamps: bool
    connected: bool

    def __init__(
        self,
        fc_addr: tuple[str, int],
        gs_addr: tuple[str, int],
        overwrite_timestamps: bool = False,
    ) -> None:
        logger.info(
            f"Limewire started (overwrite_timestamps={overwrite_timestamps})."
        )

        self.fc_addr = fc_addr
        self.gs_addr = gs_addr

        # Set up Synnax
        self.synnax_client, self.channels = synnax_init()
        self.synnax_writer = None
        self.synnax_framer = SynnaxFramer(self.channels)
        self.overwrite_timestamps = overwrite_timestamps

        # Set up framers and message queue
        self.lmp_framer = None
        self.fc_telemetry_framer = None
        self.gs_telemetry_framer = None
        self.queue = asyncio.Queue()

        # Set up state variables
        self.connected = False

    async def start(self) -> None:
        """Open a connection to the flight computer and start Limewire."""

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

            try:
                loop = asyncio.get_event_loop()

                # Set up UDP port listener
                transport, handler = await setup_udp_listener(loop, UDP_PORT)
                self.telemetry_framer = TelemetryFramer(handler)
                send_ntp_sync(*self.fc_addr, logger)
                send_ntp_sync(*self.gs_addr, logger)

                logger.info("Listening for telemetry on UDP port 6767")
            except Exception as err:
                logger.error(f"Error opening telemetry listener: {str(err)}")

            # Spawn tasks
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._synnax_write())
                tg.create_task(self._listen_handoff_channel())
                tg.create_task(self._telemetry_listen())
                tg.create_task(self._connect_fc())

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

    async def _connect_fc(self):
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
        while True:
            # Send NTP sync before connecting to ensure correct telemetry message timestamps.
            self.connected = False
            send_ntp_sync(*self.fc_addr, logger)

            try:
                logger.info(
                    f"Connecting to flight computer at {self.fc_addr[0]}:{self.fc_addr[1]}..."
                )

                self.tcp_reader, self.tcp_writer = await asyncio.wait_for(
                    asyncio.open_connection(*self.fc_addr),
                    timeout=FC_CONNECT_TIMEOUT,
                )
                self.lmp_framer = LMPFramer(self.tcp_reader, self.tcp_writer)
                self.connected = True
            except TimeoutError:
                logger.warning("Connection attempt timed out.")
                continue
            except ConnectionRefusedError:
                logger.warning(
                    f"Connection refused to flight computer at {self.fc_addr[0]}:{self.fc_addr[1]}."
                )
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

            peername = self.tcp_writer.get_extra_info("peername")  # pyright: ignore[reportAny]
            logger.info(
                f"Connected to flight computer at {peername[0]}:{peername[1]}."
            )

            # Track whether you need to reconnect
            reconnect = False
            try:
                # Set up flight tcp async tasks that are only needed when flight computer is connected
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(self._fc_tcp_read())
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
                logger.error(f"Tasks failed with {len(eg.exceptions)} error(s)")
                for exc in eg.exceptions:
                    logger.opt(exception=exc).error("Traceback: ")
            if reconnect:
                continue
            else:
                break

    async def _send_heartbeat(self):
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)

            logger.debug(f"Queue size: {self.queue.qsize()}")

            if self.lmp_framer is None:
                continue

            try:
                await self.lmp_framer.send_message(HeartbeatMessage())
            except ConnectionResetError as err:
                raise err

    async def _fc_tcp_read(self):
        """Handle incoming data from the TCP connection.

        Returns:
            The number of telemetry values processed.
        """

        # Timeout in seconds for no data received

        while True:
            if self.lmp_framer is None:
                # Yield control back to runtime
                await asyncio.sleep(0)
                continue

            try:
                # Use wait_for to implement a timeout on receive_message
                message = await asyncio.wait_for(
                    self.lmp_framer.receive_message(), timeout=FC_READ_TIMEOUT
                )

            except asyncio.TimeoutError:
                # No data received for READ_TIMEOUT seconds
                logger.error(
                    f"No data received from flight computer for {FC_READ_TIMEOUT} seconds. "
                    "Connection may be lost."
                )
                raise ConnectionResetError(
                    f"Flight computer read timeout: no data for {FC_READ_TIMEOUT} seconds"
                )

            except (FramingError, ValueError) as err:
                logger.error(str(err))
                logger.opt(exception=err).debug("Traceback: ", exc_info=True)
                continue

            if message is None:
                logger.error("None type message received. Closing. ")
                break

            if type(message) is ValveStateMessage:
                await self.queue.put(message)
            elif type(message) is HeartbeatMessage:
                logger.debug("Received heartbeat response from flight computer")
            else:
                logger.warning(
                    f"Received unexpected message type: {type(message)}"
                )
                pass

    async def _telemetry_listen(self):
        """Listen for telemetry messages."""
        while True:
            if self.telemetry_framer is None:
                # Yield control back to runtime
                await asyncio.sleep(0)
                continue

            try:
                message = await self.telemetry_framer.receive_message()
            except (FramingError, ValueError) as err:
                logger.error(str(err))
                logger.opt(exception=err).debug("Traceback: ", exc_info=True)
                continue

            if self.overwrite_timestamps:
                message.timestamp = sy.TimeStamp.now()

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

            try:
                frame = self.synnax_framer.build_synnax_frame(message)
            except (KeyError, ValueError) as err:
                logger.error(str(err))
                self.queue.task_done()
                continue

            if frame is None:
                self.queue.task_done()
                continue

            if self.synnax_writer is None:
                try:
                    self.synnax_writer = await self._open_synnax_writer(
                        message.timestamp
                    )
                except sy.ValidationError as err:
                    logger.warning(
                        f"Synnax validation error '{str(err)}', skipping frame"
                    )
                    send_ntp_sync(*self.fc_addr, logger)
                    send_ntp_sync(*self.gs_addr, logger)
                    continue

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

                # Writer will get re-initialzed during next loop iteration
                self.synnax_writer = None

                send_ntp_sync(*self.fc_addr, logger)
                send_ntp_sync(*self.gs_addr, logger)

            self.queue.task_done()

    async def _open_synnax_writer(self, timestamp: int) -> sy.Writer:
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

    async def _listen_handoff_channel(self):
        """Signal handoff (ethernet to radio) to the FC"""
        async with await self.synnax_client.open_async_streamer(
            "handoff_channel"
        ) as streamer:
            async for frame in streamer:
                for _, series in frame.items():
                    signal = series[-1]
                    msg = HandoffMessage(signal)
                    if self.lmp_framer is None:
                        continue

                    await self.lmp_framer.send_message(msg)

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
            async for frame in streamer:
                for channel, series in frame.items():
                    valve = Valve.from_channel_name(channel)  # pyright: ignore[reportArgumentType]
                    # For now, let's assume that if multiple values are in the
                    # frame, we only care about the most recent one
                    msg = ValveCommandMessage(valve, bool(series[-1]))  # pyright: ignore[reportUnknownArgumentType]

                    if self.lmp_framer is None:
                        continue

                    await self.lmp_framer.send_message(msg)
