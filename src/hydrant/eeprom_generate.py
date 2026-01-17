import ipaddress
import struct
import zlib
from enum import Enum
from io import BytesIO

import tftpy
from loguru import logger


class ValveVoltage(Enum):
    V12 = 0  # 12V
    V24 = 1  # 24V


class TCGain(Enum):
    X1 = 0
    X2 = 1
    X4 = 2
    X8 = 3
    X16 = 4
    X32 = 5
    X64 = 6
    X128 = 7

    @classmethod
    def from_int(cls, gain: int):
        if gain == 1:
            return TCGain.X1
        elif gain == 2:
            return TCGain.X2
        elif gain == 4:
            return TCGain.X4
        elif gain == 8:
            return TCGain.X8
        elif gain == 16:
            return TCGain.X16
        elif gain == 32:
            return TCGain.X32
        elif gain == 64:
            return TCGain.X64
        elif gain == 128:
            return TCGain.X128
        else:
            raise Exception("TC gain must be a power of 2 from 1 to 128")


class PT:
    def __init__(self, range: float, offset: float, max: float):
        self.range = range
        self.offset = offset
        self.max_voltage = max


class TC:
    def __init__(self, gain: TCGain):
        self.gain = gain


class VLV:
    def __init__(self, voltage: ValveVoltage, enabled: bool):
        self.voltage = voltage
        self.enabled = enabled


def generate_bb_eeprom(
    bb_num: int,
    fc_ip: ipaddress.IPv4Address,
    bb_ip: ipaddress.IPv4Address,
    pts: list[PT],
    tcs: list[TC],
    vlvs: list[VLV],
) -> bytes:
    if len(pts) != 10:
        raise ValueError(
            "Bay Board must be configured with exactly 10 PT channels"
        )
    if len(tcs) != 6:
        raise ValueError(
            "Bay Board must be configured with exactly 6 TC channels"
        )
    if len(vlvs) != 5:
        raise ValueError(
            "Bay Board must be configured with exactly 5 valve channels"
        )
    if bb_num < 1 or bb_num > 3:
        raise ValueError("Bay Board must be configured as BB1 through BB3")
    raw_out = struct.pack("<B", bb_num)
    for x in pts:
        raw_out += (
            struct.pack("<f", x.offset)
            + struct.pack("<f", x.range)
            + struct.pack("<f", x.max_voltage)
        )
    for x in tcs:
        raw_out += struct.pack("<B", x.gain.value)
    for x in vlvs:
        raw_out += struct.pack("<B", x.voltage.value) + struct.pack(
            "<B", int(x.enabled)
        )
    raw_out += fc_ip.packed + bb_ip.packed

    crc = zlib.crc32(raw_out)

    raw_out += struct.pack("<I", crc)
    return raw_out


def generate_fr_eeprom(
    fc_ip: ipaddress.IPv4Address, fr_ip: ipaddress.IPv4Address
):
    logger.warning("Flight Recorder doesn't exist yet :(")
    raise NotImplementedError(
        "Can't do this man, actually this shouldn't be possible"
    )


def generate_fc_eeprom(
    pts: list[PT],
    tcs: list[TC],
    vlvs: list[VLV],
    limewire_IP: ipaddress.IPv4Address,
    fc_ip: ipaddress.IPv4Address,
    bb1_ip: ipaddress.IPv4Address,
    bb2_ip: ipaddress.IPv4Address,
    bb3_ip: ipaddress.IPv4Address,
    fr_ip: ipaddress.IPv4Address,
) -> bytes:
    if len(pts) != 5:
        raise ValueError(
            "Flight Computer must be configured with exactly 5 PT channels"
        )
    if len(tcs) != 3:
        raise ValueError(
            "Flight Computer must be configured with exactly 3 TC channels"
        )
    if len(vlvs) != 3:
        raise ValueError(
            "Flight Computer must be configured with exactly 3 valve channels"
        )
    raw_out = bytes()
    for x in pts:
        raw_out += (
            struct.pack("<f", x.offset)
            + struct.pack("<f", x.range)
            + struct.pack("<f", x.max_voltage)
        )
    for x in tcs:
        raw_out += struct.pack("<B", x.gain.value)
    for x in vlvs:
        raw_out += struct.pack("<B", x.voltage.value) + struct.pack(
            "<B", int(x.enabled)
        )
    raw_out += (
        limewire_IP.packed
        + fc_ip.packed
        + bb1_ip.packed
        + bb2_ip.packed
        + bb3_ip.packed
        + fr_ip.packed
    )

    crc = zlib.crc32(raw_out)

    raw_out += struct.pack("<I", crc)
    return raw_out


def send_eeprom_tftp(board: ipaddress.IPv4Address, content: bytes):
    logger.info("Sending eeprom config over TFTP to " + str(board))
    tftp_client = tftpy.TftpClient(str(board))
    tftp_client.upload("eeprom.bin", BytesIO(content))


def configure_fc(
    pts, tcs, vlvs, gseip, fcip, bb1ip, bb2ip, bb3ip, frip, tftpip, log=logger
):
    eeprom_content = generate_fc_eeprom(
        pts, tcs, vlvs, gseip, fcip, bb1ip, bb2ip, bb3ip, frip
    )
    send_eeprom_tftp(tftpip, eeprom_content)


def configure_bb(bb_num, pts, tcs, vlvs, fcip, bbip, tftpip):
    eeprom_content = generate_bb_eeprom(bb_num, fcip, bbip, pts, tcs, vlvs)
    send_eeprom_tftp(tftpip, eeprom_content)


def configure_fr(fcip, frip, tftpip):
    eeprom_content = generate_fr_eeprom(fcip, frip)
    send_eeprom_tftp(tftpip, eeprom_content)
