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

        # Server information
        self.server_ip_addr = server_addr[0]
        self.server_port = server_addr[1]
        self.client_writers: set[asyncio.StreamWriter] = set()

    async def start_server(self):
        server = await asyncio.start_server(
            partial(self.handle_client),
            self.server_ip_addr,
            self.server_port,
        )

        addr = server.sockets[0].getsockname()
        print(f"Proxy server serving on {format_socket_address(addr)}.")

        async with server:
            await server.serve_forever()

    async def _broadcast_fc_data(self, msg: bytes) -> None:
        for client in list(self.client_writers):
            client.write(msg)
            await client.drain()

    async def handle_client(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
    ):
        # Add the writer to the set
        self.client_writers.add(client_writer)

        async def client_read_loop():
            while True:
                # Read the client data
                msg_length = await client_reader.read(1)
                if not msg_length:
                    break

                msg_length = int.from_bytes(msg_length)
                msg_bytes = await client_reader.readexactly(msg_length)
                if not msg_bytes:
                    break

                # Write to flight computer
                self.fc_writer.write(msg_length.to_bytes(1) + msg_bytes)
                await self.fc_writer.drain()

            # Clean up on loop end
            self.client_writers.discard(client_writer)
            client_writer.close()
            await client_writer.wait_closed()

        asyncio.create_task(client_read_loop())

    async def _send_heartbeat(self):
        HEARTBEAT_INTERVAL = 1
        while True:
            try:
                msg = HeartbeatMessage()
                msg_bytes = bytes(msg)

                self.fc_writer.write(msg_bytes)
                await self.fc_writer.drain()
                await asyncio.sleep(HEARTBEAT_INTERVAL)
            except ConnectionResetError as err:
                raise err

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
            self.server_started = False
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

                peername = self.fc_writer.get_extra_info("peername")
                print(
                    f"Connected to flight computer at {peername[0]}:{peername[1]}."
                )

                # Initalize CSV output for diff latencies
                self._init_output()

                # Set up async tasks
                self.start_time = asyncio.get_event_loop().time()
                # Track whether you need to reconnect
                reconnect = False
                try:
                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self._fc_read())
                        tg.create_task(self._send_heartbeat())
                        if not self.server_started:
                            self.server_started = True
                            tg.create_task(self.start_server())
                except* ConnectionResetError:
                    print("Connection to flight computer lost")
                    reconnect = True
                    # Disconnect the clients
                    for client_writer in self.client_writers:
                        self.client_writers.discard(client_writer)
                        client_writer.close()
                        await client_writer.wait_closed()

                except* Exception as eg:
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

    async def stop(self) -> None:
        """Run shutdown code."""

        self.fc_writer.close()
        await self.fc_writer.wait_closed()

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

    async def _fc_read(self) -> None:
        """Handle incoming data from the TCP connection.

        Returns:
            The number of telemetry values processed.
        """
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
            await self._broadcast_fc_data(msg_bytes)

    def print_latency_stats(self) -> None:
        # Latency stats + histogram
        if len(self.diff_values_ns) > 0:
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
            # Ensure axis shows plain ns, not scientific offset (e.g., x1e6)
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

    def _parse_and_record(self, msg_bytes: bytes) -> None:
        msg_id = int.from_bytes(msg_bytes[0:1])
        match msg_id:
            case TelemetryMessage.MSG_ID:
                msg = TelemetryMessage.from_bytes(msg_bytes)
                now_ns = int(sy.TimeStamp.now())
                fc_ns = msg.timestamp
                latency_ns = now_ns - fc_ns

                self.diff_values_ns.append(latency_ns)
                self._write_row(
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
                self._write_row(
                    {
                        "now_ns": now_ns,
                        "msg_ns": fc_ts_ns,
                        "diff_ns": latency_ns,
                        "board": "",
                    }
                )
                return
            case _:
                # Unknown message type; mirror Limewire behavior by raising
                raise ValueError(
                    f"Received invalid LMP message identifier: 0x{msg_id:X}"
                )

    def _init_output(self) -> None:
        # Ensure directory exists
        dirpath = os.path.dirname(self.out_path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        # Open file and create writer
        file_exists = os.path.exists(self.out_path)
        needs_header = not file_exists or os.path.getsize(self.out_path) == 0
        self._csv_file = open(
            self.out_path, mode="a", newline="", encoding="utf-8"
        )
        fieldnames = ["now_ns", "msg_ns", "diff_ns", "board"]
        self._csv_writer = csv.DictWriter(self._csv_file, fieldnames=fieldnames)
        if needs_header:
            self._csv_writer.writeheader()
            self._csv_file.flush()

    def _write_row(self, row: dict) -> None:
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
