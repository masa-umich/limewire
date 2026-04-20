import base64
import csv
import json
import pathlib

from lmp.telemetry import TelemetryMessage
from lmp.valve import ValveStateMessage

MSG_TELEMETRY_VALVE = 0x1D
MSG_LOG = 0x1E


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

    def parse(self):
        """Parse dump files and write to log/telem/valve state files for specific board"""
        # With guarantees closure
        with (
            open(self.dump_file, "rb") as dump,
            open(self.log_file, "w", encoding="utf-8") as log,
            open(self.telem_file, "w", newline="", encoding="utf-8") as telem,
            open(
                self.valve_state_file,
                "w",
                newline="",
                encoding="utf-8",
            ) as valve,
        ):
            valve_csv = csv.writer(valve)
            telem_csv = csv.writer(telem)
            channel_list = None
            board = None

            count = 0
            good_count = 0

            telem_header_written = False
            valve_header_written = False
            for line in dump:
                count += 1
                if not line:
                    continue
                msg_type = line[0]
                if msg_type not in (MSG_TELEMETRY_VALVE, MSG_LOG):
                    continue

                bstr = line[1:].strip()
                if not bstr.isascii():
                    continue

                if msg_type == MSG_LOG:
                    try:
                        log.write(bstr.decode() + "\n")
                        good_count += 1
                    except Exception:
                        continue
                elif msg_type == MSG_TELEMETRY_VALVE:
                    try:
                        packet_data = base64.b64decode(bstr)[1:]
                        if packet_data[0] == TelemetryMessage.MSG_ID:
                            telem_valve_msg = TelemetryMessage.from_bytes(
                                packet_data
                            )
                        elif packet_data[0] == ValveStateMessage.MSG_ID:
                            telem_valve_msg = ValveStateMessage.from_bytes(
                                packet_data
                            )
                        else:
                            continue
                    except Exception:
                        continue

                    if isinstance(telem_valve_msg, TelemetryMessage):
                        if not telem_header_written:
                            board = telem_valve_msg.board
                            channel_list = self.channels[board.index_channel][
                                :-1
                            ]
                            telem_csv.writerow(
                                [board.index_channel] + channel_list
                            )
                            telem_header_written = True

                        telem_csv.writerow(
                            [telem_valve_msg.timestamp] + telem_valve_msg.values
                        )
                        good_count += 1
                    else:
                        if not valve_header_written:
                            assert telem_valve_msg.valve.board == board
                            valve_csv.writerow(["Valve", "Timestamp", "State"])
                            valve_header_written = True
                        valve_csv.writerow(
                            [
                                telem_valve_msg.valve,
                                telem_valve_msg.timestamp,
                                telem_valve_msg.state,
                            ]
                        )
                        good_count += 1

            if count > 0:
                print(
                    f"Corrupted message percent: {(count - good_count) * 100 / count} ({count - good_count} corrupted messages)"
                )
            else:
                print("Dump file empty")
