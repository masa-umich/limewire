import asyncio
from asyncio.streams import StreamReader, StreamWriter
from pprint import pprint

import synnax as sy

from limewire.messages.valve import ValveStateMessage

from .messages import TelemetryMessage
from .util import get_write_time_channel_name, synnax_init


class Limewire:
    """A class to manage Limewire's resources."""

    def __init__(self) -> None:
        self.synnax_client, self.channels = synnax_init()
        self.synnax_writer = None
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def start(self, fc_addr: tuple[str, int]) -> None:
        """Open a connection to the flight computer and start Limewire.

        Args:
            fc_addr: A tuple (ip_addr, port) indicating the flight
                computer's TCP socket address.
        """
        self.tcp_reader, self.tcp_writer = await self._connect_fc(*fc_addr)

        peername = self.tcp_writer.get_extra_info("peername")
        print(f"Connected to flight computer at {peername[0]}:{peername[1]}.")

        # Set up async tasks
        recv_task = asyncio.create_task(self._tcp_read())
        write_task = asyncio.create_task(self._synnax_write())
        start_time = asyncio.get_event_loop().time()

        # Clean up resources after tasks complete
        values_processed = await recv_task
        await self.queue.join()
        write_task.cancel()
        if self.synnax_writer is not None:
            self.synnax_writer.close()
        self.tcp_writer.close()
        await self.tcp_writer.wait_closed()

        # Print statistics
        runtime = asyncio.get_event_loop().time() - start_time
        if values_processed == 0:
            print("Unable to receive data from flight computer!")
        else:
            print(
                f"Processed {values_processed} values in {runtime:.2f} sec ({values_processed / runtime:.2f} values/sec)"
            )

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

    async def _tcp_read(self) -> int:
        """Handle incoming data from the TCP connection.

        Returns:
            The number of telemetry values processed.
        """
        values_processed = 0
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
                    values_processed += num_values
                case _:
                    raise ValueError(
                        f"Received invalid LMP message identifier: 0x{msg_id:X}"
                    )

        return values_processed

    async def _synnax_write(self) -> None:
        """Write telemetry data and valve state data to Synnax."""
        while True:
            # Parse message bytes into TelemetryMessage
            msg_bytes = await self.queue.get()
            msg_id = int.from_bytes(msg_bytes[0:1])

            if msg_id == TelemetryMessage.MSG_ID:
                msg = TelemetryMessage.from_bytes(msg_bytes)
                frame = self._build_telemetry_frame(msg)
            else:
                msg = ValveStateMessage.from_bytes(msg_bytes)
                frame = self._build_valve_state_frame(msg)

            if self.synnax_writer is None:
                self.synnax_writer = self._open_synnax_writer(msg.timestamp)

            self.synnax_writer.write(frame)  # pyright: ignore[reportArgumentType]

            self.queue.task_done()

    def _build_telemetry_frame(self, msg: TelemetryMessage) -> dict:
        """Construct a frame to write to Synnax from a telemetry message."""

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
        frame[msg.valve.state_channel] = msg.state
        limewire_write_time_channel = get_write_time_channel_name(
            msg.valve.state_channel_index
        )
        frame[limewire_write_time_channel] = sy.TimeStamp.now()
        return frame

    def _open_synnax_writer(self, timestamp: int) -> sy.Writer:
        """Return an initialized Synnax writer using the given timestamp."""

        # Create a list of all channels
        writer_channels = []
        for index_channel, data_channels in self.channels.items():
            writer_channels.append(index_channel)
            for ch in data_channels:
                writer_channels.append(ch)

        return self.synnax_client.open_writer(
            start=timestamp,
            channels=writer_channels,
            enable_auto_commit=True,
        )
