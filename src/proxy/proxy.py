import asyncio
import csv
import os
import statistics
import traceback
from contextlib import asynccontextmanager
from functools import partial
from typing import Tuple

import seaborn as sns
import synnax as sy
from matplotlib import pyplot as plt
from matplotlib.ticker import ScalarFormatter

from lmp import HeartbeatMessage, TelemetryMessage, ValveStateMessage


def format_socket_address(addr: Tuple[str, int]) -> str:
    """Format of addr: [address, port]"""

    return addr[0] + ":" + str(addr[1])


class Proxy:
    def __init__(
        self,
        server_addr: tuple[str, int],
        out_path: str = "proxy_log.csv",
    ) -> None:
        self.out_path: str = out_path

        # Latency stats
        self._csv_writer: csv.DictWriter | None = None
        self.diff_values_ns: list[float] = []
        # Initalize CSV output for diff latencies
        self._init_output()

        # Server information
        self.server_addr = server_addr
        self.client_writers: set[asyncio.StreamWriter] = set()

    async def handle_client(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
    ):
        # Reject connections if FC is not connected yet
        if not self.connected:
            client_writer.close()
            await client_writer.wait_closed()
            return

        # Add the writer to the set
        index = len(self.client_writers)

        self.client_writers.add(client_writer)

        @asynccontextmanager
        async def lifespan():
            try:
                yield
            finally:
                # Clean up on disconnect
                self.client_writers.discard(client_writer)
                client_writer.close()
                await client_writer.wait_closed()

        async with lifespan():
            peername = client_writer.get_extra_info("peername")
            print(
                f"Connected to client {index} at {peername[0]}:{peername[1]}."
            )

            try:
                await asyncio.create_task(self.client_read_loop(client_reader))
            except* (
                ConnectionResetError,
                ConnectionAbortedError,
            ):
                print(f"Connection to client {index} lost")
            except* Exception as eg:
                print("=" * 60)
                print(f"Tasks failed with {len(eg.exceptions)} error(s)")
                for exc in eg.exceptions:
                    print("=" * 60)
                    traceback.print_exception(type(exc), exc, exc.__traceback__)
                print("=" * 60)

    async def client_read_loop(
        self,
        client_reader: asyncio.StreamReader,
    ):
        while True:
            # Read the client data
            msg_length = await client_reader.read(1)
            if not msg_length:
                break

            msg_length = int.from_bytes(msg_length)
            msg_bytes = await client_reader.readexactly(msg_length)
            if not msg_bytes:
                break

            if self.connected:
                self.fc_writer.write(msg_length.to_bytes(1) + msg_bytes)
                await self.fc_writer.drain()
            else:
                break

    async def disconnect_clients(self):
        # Disconnect the clients
        for client_writer in self.client_writers:
            client_writer.close()
            await client_writer.wait_closed()
        # Clear the set
        self.client_writers.clear()

    async def _connect_fc(
        self, ip_addr: str, port: int
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
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

    async def start(self, fc_addr: tuple[str, int]) -> None:
        # We need to define an asynccontextmanager to ensure that shutdown
        # code runs after the task is canceled because of e.g. Ctrl+C
        @asynccontextmanager
        async def lifespan():
            try:
                yield
            finally:
                await self.stop()

        async with lifespan():
            self.connected = False
            while True:
                try:
                    print(
                        f"Connecting to flight computer at {fc_addr[0]}:{fc_addr[1]}..."
                    )

                    self.fc_reader, self.fc_writer = await self._connect_fc(
                        *fc_addr
                    )
                    self.connected = True
                except ConnectionRefusedError:
                    await asyncio.sleep(1)
                    continue

                # Start server here
                self.server = await asyncio.start_server(
                    partial(self.handle_client),
                    *self.server_addr,
                )

                addr = self.server.sockets[0].getsockname()
                print(f"Proxy server serving on {format_socket_address(addr)}.")
                # Server forever, even if fight computer connection is severed
                await self.server.start_serving()

                peername = self.fc_writer.get_extra_info("peername")
                print(
                    f"Connected to flight computer at {peername[0]}:{peername[1]}."
                )

                # Set up async tasks
                self.start_time = asyncio.get_event_loop().time()
                # Track whether you need to reconnect
                reconnect = False
                try:
                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self._fc_read())
                        tg.create_task(self._send_heartbeat())
                except* (ConnectionResetError, ConnectionAbortedError):
                    print("Connection to flight computer lost")
                    self.connected = False
                    reconnect = True
                    # Disconnect the clients
                    await self.disconnect_clients()

                    # Close server
                    self.server.close()
                    await self.server.wait_closed()
                except* Exception as eg:
                    self.connected = False
                    print("=" * 60)
                    print(f"Tasks failed with {len(eg.exceptions)} error(s)")
                    for exc in eg.exceptions:
                        print("=" * 60)
                        traceback.print_exception(
                            type(exc), exc, exc.__traceback__
                        )
                    print("=" * 60)
                if reconnect:
                    continue
                else:
                    break

    async def _send_heartbeat(self):
        HEARTBEAT_INTERVAL = 1
        cnt = 0
        while True:
            try:
                cnt += 1
                msg = HeartbeatMessage()
                msg_bytes = bytes(msg)

                self.fc_writer.write(len(msg_bytes).to_bytes(1) + msg_bytes)
                await self.fc_writer.drain()
                await asyncio.sleep(HEARTBEAT_INTERVAL)
            except (ConnectionResetError, ConnectionAbortedError) as err:
                raise err
            except Exception as err:
                print("unknown heartbeat error", err)

    async def _fc_read(self) -> None:
        """Handle incoming data from the TCP connection.

        Returns:
            The number of telemetry values processed.
        """

        async def _broadcast_fc_data(msg: bytes) -> None:
            for client in list(self.client_writers):
                client.write(msg)
                await client.drain()

        self.values_processed = 0
        while True:
            msg_length = await self.fc_reader.read(1)
            if not msg_length:
                break

            msg_length = int.from_bytes(msg_length)
            msg_bytes = await self.fc_reader.readexactly(msg_length)
            if not msg_bytes:
                break

            msg_id = int.from_bytes(msg_bytes[0:1])
            match msg_id:
                case TelemetryMessage.MSG_ID:
                    self._parse_and_record(msg_bytes)
                    self.values_processed += 1
                case ValveStateMessage.MSG_ID:
                    self._parse_and_record(msg_bytes)
                    self.values_processed += 1
                case _:
                    raise ValueError(
                        f"Received invalid LMP message identifier: 0x{msg_id:X}"
                    )
            # Broadcast to connected clients
            await _broadcast_fc_data(msg_length.to_bytes(1) + msg_bytes)

    async def stop(self) -> None:
        """Run shutdown code."""
        print("stopping")
        self.connected = False

        self.fc_writer.close()
        await self.fc_writer.wait_closed()

        await self.disconnect_clients()

        # Disconnect clients and close server
        self.server.close()
        await self.server.wait_closed()

        # Close CSV file
        self._csv_file.close()

        runtime = asyncio.get_event_loop().time() - self.start_time
        if self.values_processed == 0:
            print("No data received from flight computer.")
        else:
            print(
                f"Processed {self.values_processed} values in {runtime:.2f} sec "
                f"({self.values_processed / runtime:.2f} values/sec)"
            )
            self.print_latency_stats()

    def print_latency_stats(self) -> None:
        """Print latency stats upon closing the program and write to histogram"""
        # Latency stats + histogram
        if len(self.diff_values_ns) > 0:
            # CONVERT TO MS
            diff_values_ms = [x / 10**6 for x in self.diff_values_ns]
            avg_ms = statistics.mean(diff_values_ms)
            std_ms = (
                statistics.stdev(diff_values_ms)
                if len(diff_values_ms) > 1
                else 0.0
            )
            print(f"Average latency (ms): {avg_ms}")
            print(f"Std latency (ms): {std_ms}")
            print(f"Max (ms): {max(diff_values_ms)}")
            sns.set(style="whitegrid")
            plt.figure(figsize=(9, 5))
            ax = sns.histplot(
                diff_values_ms,
                bins="fd",
                kde=True,
                color="#4C78A8",
                edgecolor="black",
                alpha=0.85,
            )
            plt.xlabel("Latency (ms)")
            plt.ylabel("Count")
            plt.title("Latency Histogram")
            # Overlay mean and ±1σ
            xmin = min(self.diff_values_ns)
            xmax = max(self.diff_values_ns)
            ax.axvline(
                avg_ms,
                color="#E45756",
                linestyle="--",
                linewidth=1.5,
                label=f"Mean = {avg_ms:.0f} ns",
            )
            if std_ms > 0.0:
                ax.axvline(
                    avg_ms - std_ms,
                    color="#F58518",
                    linestyle=":",
                    linewidth=1.2,
                    label=f"-1σ = {avg_ms - std_ms:.0f} ns",
                )
                ax.axvline(
                    avg_ms + std_ms,
                    color="#F58518",
                    linestyle=":",
                    linewidth=1.2,
                    label=f"+1σ = {avg_ms + std_ms:.0f} ns",
                )

            ax.xaxis.set_major_formatter(ScalarFormatter(useOffset=False))
            ax.ticklabel_format(axis="x", style="plain", useOffset=False)
            margin = max((xmax - xmin) * 0.05, 1.0)
            plt.xlim(xmin - margin, xmax + margin)
            plt.legend()
            plt.tight_layout()
            base, _ = os.path.splitext(self.out_path)
            hist_path = f"{base}_hist.png"
            plt.savefig(hist_path, dpi=160)
            plt.close()
            print(f"Saved histogram: {hist_path}")

    def _parse_and_record(self, msg_bytes: bytes) -> None:
        """Write latency data to CSV file"""

        # Write helper
        def write_row(row: dict) -> None:
            if self._csv_writer is None:
                return
            # Ensure all fields present
            safe_row = {
                "now_ns": row.get("now_ns", ""),
                "msg_ns": row.get("msg_ns", ""),
                "diff_ns": row.get("diff_ns", ""),
                "board": row.get("board", ""),
            }
            self._csv_writer.writerow(safe_row)
            self._csv_file.flush()

        msg_id = int.from_bytes(msg_bytes[0:1])
        match msg_id:
            case TelemetryMessage.MSG_ID:
                msg = TelemetryMessage.from_bytes(msg_bytes)
                now_ns = int(sy.TimeStamp.now())
                fc_ns = msg.timestamp
                latency_ns = now_ns - fc_ns

                self.diff_values_ns.append(latency_ns)
                write_row(
                    {
                        "now_ns": now_ns,
                        "msg_ns": fc_ns,
                        "diff_ns": latency_ns,
                        "board": msg.board.name,
                    }
                )
                return
            case ValveStateMessage.MSG_ID:
                msg = ValveStateMessage.from_bytes(msg_bytes)
                fc_ts_ns = msg.timestamp
                now_ns = int(sy.TimeStamp.now())
                latency_ns = now_ns - fc_ts_ns

                self.diff_values_ns.append(latency_ns)
                write_row(
                    {
                        "now_ns": now_ns,
                        "msg_ns": fc_ts_ns,
                        "diff_ns": latency_ns,
                        "board": "",
                    }
                )
                return
            case _:
                # Unknown message type
                raise ValueError(
                    f"Received invalid LMP message identifier: 0x{msg_id:X}"
                )

    def _init_output(self) -> None:
        """Initalize the CSV file to track latency stats"""
        # Ensure directory exists
        dirpath = os.path.dirname(self.out_path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        # Open file and create writer
        needs_header = (
            not os.path.exists(self.out_path)
            or os.path.getsize(self.out_path) == 0
        )
        self._csv_file = open(
            self.out_path, mode="a", newline="", encoding="utf-8"
        )
        fieldnames = ["now_ns", "msg_ns", "diff_ns", "board"]
        self._csv_writer = csv.DictWriter(self._csv_file, fieldnames=fieldnames)

        # Write header if necessary
        if needs_header:
            self._csv_writer.writeheader()
            self._csv_file.flush()
