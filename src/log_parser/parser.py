import base64
import csv
import json
import pathlib

from lmp.telemetry import TelemetryMessage


class Parser:
    def __init__(self, file: pathlib.Path):
        self.dump_file = file
        self.telem_file = file.parent / "telemetry.csv"
        self.log_file = file.parent / "log.txt"
        channels_file = (
            pathlib.Path(__file__).parent.parent
            / "limewire"
            / "data"
            / "channels.json"
        )
        with channels_file.open() as f:
            self.channels: dict[str, list[str]] = json.load(f)
        self.parse()
        
    def parse(self):
        dump = open(self.dump_file, "rb")
        log = open(self.log_file, "w")
        telem = open(self.telem_file, "w", newline='')
        csv_telem = csv.writer(telem)
        channel_list = None
        count = 0
        good_count = 0
        for l in dump.readlines():
            count += 1
            if l[0] == 0x1D or l[0] == 0x1E:
                try:
                    bstr = l[1:].strip()
                    if bstr.isascii():
                        if l[0] == 0x1D:
                            try:
                                telem_msg = TelemetryMessage.from_bytes(base64.b64decode(bstr))
                                board = telem_msg.board
                                if channel_list is None:
                                    channel_list = self.channels[board.index_channel + "_timestamp"]
                                    channel_list = channel_list[:-2]
                                    csv_telem.writerow([board.index_channel + "_timestamp"] + channel_list)
                                csv_telem.writerow([telem_msg.timestamp] + telem_msg.values)
                                good_count += 1
                            except:
                                pass
                        else:
                            good_count += 1
                            log.write(bstr.decode() + "\n")
                except:
                    pass
        print(f"Corrupted message percent: {(count - good_count) * 100/count}")
        dump.close()
        log.close()
        telem.close()