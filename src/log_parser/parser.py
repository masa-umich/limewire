import base64
import csv
import json
import pathlib

from lmp.telemetry import TelemetryMessage
from lmp.util import Board
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
        self.valve_state_file = file.parent / f"{file.stem}_valve_state.csv"
        self.log_file = file.parent / f"{file.stem}_log.txt"

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
            open(
                self.valve_state_file,
                "w",
                newline="",
                encoding="utf-8",
            ) as valve,
        ):
            valve_csv = csv.writer(valve)
            telem_csv = {}
            board = None

            count = 0
            good_count = 0

            telem_header_written: list[Board] = []
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
                        if telem_valve_msg.board not in telem_header_written:
                            board = telem_valve_msg.board
                            board_telem_file = (
                                self.dump_file.parent
                                / f"{self.dump_file.stem}_{board.name}_telemetry.csv"
                            )
                            telem_file = open(
                                board_telem_file,
                                "w",
                                newline="",
                                encoding="utf-8",
                            )
                            telem_board_csv = csv.writer(telem_file)
                            channel_list = self.channels[board.index_channel][
                                :-1
                            ]
                            telem_board_csv.writerow(
                                [board.index_channel] + channel_list
                            )
                            telem_csv[board] = telem_board_csv
                            telem_header_written.append(telem_valve_msg.board)

                        telem_csv[telem_valve_msg.board].writerow(
                            [telem_valve_msg.timestamp] + telem_valve_msg.values
                        )
                        good_count += 1
                    else:
                        if not valve_header_written:
                            # assert telem_valve_msg.valve.board == board
                            valve_csv.writerow(
                                ["Board", "Valve", "Timestamp", "State"]
                            )
                            valve_header_written = True
                        valve_csv.writerow(
                            [
                                telem_valve_msg.valve.board.value,
                                telem_valve_msg.valve.num,
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
