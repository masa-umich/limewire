import asyncio
import csv
import os
import statistics
from contextlib import asynccontextmanager

import seaborn as sns
import synnax as sy
from matplotlib import pyplot as plt
from matplotlib.ticker import ScalarFormatter

from lmp import TelemetryMessage, ValveStateMessage


class Proxy:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8888,
        out_path: str = "proxy_log.csv",
        out_format: str = "csv",
    ) -> None:
        self.host: str = host
        self.port: int = port

        self.out_path: str = out_path
        self.out_format: str = out_format
        self._csv_writer: csv.DictWriter | None = None

        self.diff_values_ns: list[float] = []

    async def start(self) -> None:
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
                        f"Connecting to flight computer at {self.host}:{self.port}..."
                    )

                    self.tcp_reader, self.tcp_writer = await self._connect_fc(
                        self.host, self.port
                    )
                    self.connected = True
                except ConnectionRefusedError:
                    await asyncio.sleep(1)
                    continue

                peername = self.tcp_writer.get_extra_info("peername")
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
                        tg.create_task(self._tcp_read())
                except* ConnectionResetError:
                    print("Connection to flight computer lost")
                    reconnect = True
                except* Exception as eg:
                    print("=" * 60)
                    print(f"Tasks failed with {len(eg.exceptions)} error(s)")
                    # for exc in eg.exceptions:
                    #     print("=" * 60)
                    #     # traceback.print_exception(
                    #     #     type(exc), exc, exc.__traceback__
                    #     # )
                    print("=" * 60)
                if reconnect:
                    continue
                else:
                    break

    async def stop(self) -> None:
        """Run shutdown code."""

        self.tcp_writer.close()
        await self.tcp_writer.wait_closed()

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

    def print_latency_stats(self) -> None:
        # Latency stats + histogram
        if len(self.diff_values_ns) > 0:
            avg_ns = statistics.mean(self.diff_values_ns)
            std_ns = (
                statistics.stdev(self.diff_values_ns)
                if len(self.diff_values_ns) > 1
                else 0.0
            )
            print(f"Average latency (ns): {avg_ns}")
            print(f"Std latency (ns): {std_ns}")
            print(f"Max (ns): {max(self.diff_values_ns)}")
            sns.set(style="whitegrid")
            plt.figure(figsize=(9, 5))
            ax = sns.histplot(
                self.diff_values_ns,
                bins="fd",
                kde=True,
                color="#4C78A8",
                edgecolor="black",
                alpha=0.85,
            )
            plt.xlabel("Latency (ns)")
            plt.ylabel("Count")
            plt.title("Latency Histogram")
            # Overlay mean and ±1σ
            xmin = min(self.diff_values_ns)
            xmax = max(self.diff_values_ns)
            ax.axvline(
                avg_ns,
                color="#E45756",
                linestyle="--",
                linewidth=1.5,
                label=f"Mean = {avg_ns:.0f} ns",
            )
            if std_ns > 0.0:
                ax.axvline(
                    avg_ns - std_ns,
                    color="#F58518",
                    linestyle=":",
                    linewidth=1.2,
                    label=f"-1σ = {avg_ns - std_ns:.0f} ns",
                )
                ax.axvline(
                    avg_ns + std_ns,
                    color="#F58518",
                    linestyle=":",
                    linewidth=1.2,
                    label=f"+1σ = {avg_ns + std_ns:.0f} ns",
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

    async def _tcp_read(self) -> None:
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
                    self._parse_and_record(msg_bytes)
                    num_values = (len(msg_bytes) - 1 - 1 - 8) // 4
                    self.values_processed += num_values
                case ValveStateMessage.MSG_ID:
                    self._parse_and_record(msg_bytes)
                    self.values_processed += 1
                case _:
                    raise ValueError(
                        f"Received invalid LMP message identifier: 0x{msg_id:X}"
                    )

    def _parse_and_record(self, msg_bytes: bytes) -> None:
        msg_id = int.from_bytes(msg_bytes[0:1])
        match msg_id:
            case TelemetryMessage.MSG_ID:
                msg = TelemetryMessage.from_bytes(msg_bytes)
                now_ns = int(sy.TimeStamp.now())
                fc_ns = msg.timestamp
                latency_ns = now_ns - fc_ns
                # print(
                #     f"source={self.source} type=telemetry "
                #     f"board={getattr(msg.board, 'name', 'unknown')} "
                #     f"values={len(msg.values)} "
                #     f"t_fc_ns={fc_ts_ns} t_now_ns={now_ns} diff_ns={latency_ns}"
                # )
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
                # print(
                #     f"source={self.source} type=valve_state "
                #     f"valve={getattr(msg.valve, 'name', 'unknown')} "
                #     f"state={int(msg.state)} "
                #     f"t_fc_ns={fc_ts_ns} t_now_ns={now_ns} diff_ns={latency_ns}"
                # )
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
        os.makedirs(os.path.dirname(self.out_path), exist_ok=True)
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
        self._csv_writer.writerow(safe_row)  # type: ignore[union-attr]
        self._csv_file.flush()  # type: ignore[union-attr]
