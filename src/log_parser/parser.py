import base64
import csv
import json
import pathlib

from lmp.telemetry import TelemetryMessage
from lmp.util import Board
from lmp.valve import ValveStateMessage

MSG_TELEMETRY = 0x1D
MSG_LOG = 0x1E
MSG_VALVE = 0x1F


class Parser:
    dump_file: pathlib.Path
    telem_file: pathlib.Path
    log_file: pathlib.Path
    channels_file: pathlib.Path

    def __init__(self, file: pathlib.Path):
        self.dump_file = file
        self.telem_file = file.parent / "telemetry.csv"
        self.valve_state_file = file.parent / "valve_state.csv"
        self.log_file = file.parent / "log.txt"

        channels_file = (
            pathlib.Path(__file__).parent.parent
            / "limewire"
            / "data"
            / "channels.json"
        )

        with channels_file.open() as f:
            self.channels: dict[str, list[str]] = json.load(f)

    def parse(self, board: Board):
        """Parse dump files and write to log/telem files for specific board"""
        # With guarantees closure
        with (
            open(self.dump_file / board.name, "rb") as dump,
            open(self.log_file / board.name, "w", encoding="utf-8") as log,
            open(
                self.telem_file / board.name, "w", newline="", encoding="utf-8"
            ) as telem,
            open(
                self.valve_state_file / board.name,
                "w",
                newline="",
                encoding="utf-8",
            ) as valve,
        ):
            valve_csv = csv.writer(valve)
            telem_csv = csv.writer(telem)

            count = 0
            good_count = 0

            channel_list = self.channels[board.index_channel][:-1]
            telem_csv.writerow([board.index_channel] + channel_list)
            valve_csv.writerow(["Valve", "State", "Timestamp"])

            # telem_header_written = False
            for line in dump:
                count += 1
                if not line:
                    continue
                msg_type = line[0]
                if msg_type not in (MSG_TELEMETRY, MSG_LOG):
                    continue

                bstr = line[1:].strip()
                if not bstr.isascii():
                    continue

                if msg_type == MSG_LOG:
                    good_count += 1
                    log.write(bstr.decode() + "\n")
                elif msg_type == MSG_TELEMETRY:
                    try:
                        packet_data = base64.b64decode(bstr)[1:]
                        telem_msg = TelemetryMessage.from_bytes(packet_data)

                        telem_csv.writerow(
                            [telem_msg.timestamp] + telem_msg.values
                        )
                        good_count += 1
                    except Exception:
                        pass
                elif msg_type == MSG_VALVE:
                    try:
                        packet_data = base64.b64decode(bstr)[1:]
                        valve_msg = ValveStateMessage.from_bytes(packet_data)
                        valve_csv.writerow(
                            [
                                valve_msg.valve,
                                valve_msg.state,
                                valve_msg.timestamp,
                            ]
                        )
                        good_count += 1
                    except Exception:
                        pass

            if count > 0:
                print(
                    f"Corrupted message percent: {(count - good_count) * 100 / count}"
                )
            else:
                print("Dump file empty")
