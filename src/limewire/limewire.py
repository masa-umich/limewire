import asyncio
from asyncio.streams import StreamReader, StreamWriter
from contextlib import asynccontextmanager

import synnax as sy
from loguru import logger

from lmp import (
    HeartbeatMessage,
    TelemetryMessage,
    Valve,
    ValveCommandMessage,
    ValveStateMessage,
)

from .util import get_write_time_channel_name, synnax_init


class Limewire:
    """A class to manage Limewire's resources."""

    def __init__(self) -> None:
        logger.info("Limewire started.")

        self.synnax_client, self.channels = synnax_init()
        self.synnax_writer = None
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()

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

            self.connected = False
            while True:
                try:
                    logger.info(
                        f"Connecting to flight computer at {fc_addr[0]}:{fc_addr[1]}..."
                    )

                    self.tcp_reader, self.tcp_writer = await self._connect_fc(
                        *fc_addr
                    )
                    self.connected = True
                except (ConnectionRefusedError, ConnectionResetError):
                    await asyncio.sleep(1)
                    continue

                peername = self.tcp_writer.get_extra_info("peername")
                logger.info(
                    f"Connected to flight computer at {peername[0]}:{peername[1]}."
                )

                # Set up async tasks
                self.start_time = asyncio.get_event_loop().time()
                # Track whether you need to reconnect
                reconnect = False
                try:
                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self._tcp_read())
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

    async def _send_heartbeat(self):
        HEARTBEAT_INTERVAL = 1
        while True:
            try:
                msg = HeartbeatMessage()
                msg_bytes = bytes(msg)

                self.tcp_writer.write(msg_bytes)
                await self.tcp_writer.drain()
                await asyncio.sleep(HEARTBEAT_INTERVAL)
            except ConnectionResetError as err:
                raise err
                # print(err)

    async def stop(self):
        """Run shutdown code."""

        self.tcp_writer.close()
        await self.tcp_writer.wait_closed()

        if self.synnax_writer is not None:
            self.synnax_writer.close()

        # Print statistics
        # print()  # Add extra newline after Ctrl+C
        runtime = asyncio.get_event_loop().time() - self.start_time
        if self.values_processed == 0:
            logger.warning("Unable to receive data from flight computer!")
        else:
            logger.info(
                f"Processed {self.values_processed} values in {runtime:.2f} sec ({self.values_processed / runtime:.2f} values/sec)"
            )

        logger.info("=" * 60)

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

    async def _tcp_read(self):
        """Handle incoming data from the TCP connection.

        Returns:
            The number of telemetry values processed.
        """
        self.values_processed = 0
        while True:
            msg_length = await self.tcp_reader.read(1)
            if not msg_length:
                break

            msg_length = int.from_bytes(msg_length)
            msg_bytes = await self.tcp_reader.readexactly(msg_length)
            if not msg_bytes:
                break

            msg_id = int.from_bytes(msg_bytes[0:1])
            match msg_id:
                case TelemetryMessage.MSG_ID:
                    await self.queue.put(msg_bytes)
                    num_values = (len(msg_bytes) - 1 - 1 - 8) // 4
                    self.values_processed += num_values
                case ValveStateMessage.MSG_ID:
                    await self.queue.put(msg_bytes)
                    self.values_processed += 1
                case _:
                    raise ValueError(
                        f"Received invalid LMP message identifier: 0x{msg_id:X}"
                    )

    async def _synnax_write(self) -> None:
        """Write telemetry data and valve state data to Synnax."""
        while True:
            # Parse message bytes into TelemetryMessage
            msg_bytes = await self.queue.get()
            msg_id = int.from_bytes(msg_bytes[0:1])

            if msg_id == TelemetryMessage.MSG_ID:
                msg = TelemetryMessage.from_bytes(msg_bytes)

                try:
                    frame = self._build_telemetry_frame(msg)
                except KeyError as err:
                    logger.error(str(err), extra={"error_code": "0006"})
                    self.queue.task_done()
                    continue
            else:
                msg = ValveStateMessage.from_bytes(msg_bytes)
                frame = self._build_valve_state_frame(msg)

            if self.synnax_writer is None:
                self.synnax_writer = await self._open_synnax_writer(
                    msg.timestamp
                )
            self.synnax_writer.write(frame)

            self.queue.task_done()

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

        authorities = []
        for channel in writer_channels:
            # Schematic and/or autosequences should maintain control
            # of command channels, and Limewire should have absolute
            # authority of all other channels.
            if "cmd" in channel:
                authorities.append(0)
            else:
                authorities.append(255)

        writer = self.synnax_client.open_writer(
            start=timestamp,
            channels=writer_channels,
            enable_auto_commit=True,
            authorities=authorities,
        )

        return writer

    async def _relay_valve_cmds(self):
        """Relay valve commands from Synnax to the flight computer."""

        # Create a list of all valve command channels
        cmd_channels = []
        for data_channels in self.channels.values():
            for channel in data_channels:
                if (
                    "cmd" in channel
                    and "timestamp" not in channel
                    and "limewire" not in channel
                ):
                    cmd_channels.append(channel)

        async with await self.synnax_client.open_async_streamer(
            cmd_channels
        ) as streamer:
            async for frame in streamer:
                for channel, series in frame.items():
                    valve = Valve.from_channel_name(channel)  # pyright: ignore[reportArgumentType]
                    # For now, let's assume that if multiple values are in the
                    # frame, we only care about the most recent one
                    msg = ValveCommandMessage(valve, bool(series[-1]))
                    msg_bytes = bytes(msg)

                    self.tcp_writer.write(
                        len(msg_bytes).to_bytes(1) + msg_bytes
                    )
                    await self.tcp_writer.drain()
