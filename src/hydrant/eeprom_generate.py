from enum import Enum
import ipaddress
import struct
import zlib

import tftpy

from io import BytesIO

class ValveVoltage(Enum):
    Valve_12V = 0
    Valve_24V = 1

class TCGain(Enum):
    Gain_1x = 0
    Gain_2x = 1
    Gain_4x = 2
    Gain_8x = 3
    Gain_16x = 4
    Gain_32x = 5
    Gain_64x = 6
    Gain_128x = 7
    
def TC_gain_convert(gain: int) -> TCGain:
    if(gain == 1):
        return TCGain.Gain_1x
    elif(gain == 2):
        return TCGain.Gain_2x
    elif(gain == 4):
        return TCGain.Gain_4x
    elif(gain == 8):
        return TCGain.Gain_8x
    elif(gain == 16):
        return TCGain.Gain_16x
    elif(gain == 32):
        return TCGain.Gain_32x
    elif(gain == 64):
        return TCGain.Gain_64x
    elif(gain == 128):
        return TCGain.Gain_128x
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
    def __init__(self, voltage: ValveVoltage, enabled: int):
        self.voltage = voltage
        self.enabled = enabled
        
def generate_bb_eeprom(bb_num: int, FC_IP: ipaddress.IPv4Address, BB_IP: ipaddress.IPv4Address, PTs: list[PT], TCs: list[TC], VLVs: list[VLV]) -> bytes:
    if(len(PTs) != 10):
        raise Exception("Bay Board must be configured with exactly 10 PT channels")
    if(len(TCs) != 6):
        raise Exception("Bay Board must be configured with exactly 6 TC channels")
    if(len(VLVs) != 5):
        raise Exception("Bay Board must be configured with exactly 5 valve channels")
    if(bb_num < 1 or bb_num > 3):
        raise Exception("Bay Board must be configured as BB1 through BB3")
    raw_out = struct.pack('<B', bb_num)
    for x in PTs:
        raw_out += struct.pack('<f', x.offset) + struct.pack('<f', x.range) + struct.pack('<f', x.max_voltage)
    for x in TCs:
        raw_out += struct.pack('<B', x.gain.value)
    for x in VLVs:
        raw_out += struct.pack('<B', x.voltage.value) + struct.pack('<B', x.enabled)
    raw_out += FC_IP.packed + BB_IP.packed
    
    crc = zlib.crc32(raw_out)

    raw_out += struct.pack('<I', crc)
    return raw_out
    
def generate_fr_eeprom(FCIP: ipaddress.IPv4Address, FRIP: ipaddress.IPv4Address):
    print("Flight Recorder doesn't exist yet :(")
    raise Exception("Can't do this man, actually this shouldn't be possible")
    
def generate_fc_eeprom(PTs: list[PT], TCs: list[TC], VLVs: list[VLV], limewire_IP: ipaddress.IPv4Address,
                    FC_IP: ipaddress.IPv4Address,
                    BB1_IP: ipaddress.IPv4Address,
                    BB2_IP: ipaddress.IPv4Address,
                    BB3_IP: ipaddress.IPv4Address,
                    FR_IP: ipaddress.IPv4Address) -> bytes:
    if(len(PTs) != 5):
        raise Exception("Flight Computer must be configured with exactly 5 PT channels")
    if(len(TCs) != 3):
        raise Exception("Flight Computer must be configured with exactly 3 TC channels")
    if(len(VLVs) != 3):
        raise Exception("Flight Computer must be configured with exactly 3 valve channels")
    raw_out = bytes()
    for x in PTs:
        raw_out += struct.pack('<f', x.offset) + struct.pack('<f', x.range) + struct.pack('<f', x.max_voltage)
    for x in TCs:
        raw_out += struct.pack('<B', x.gain.value)
    for x in VLVs:
        raw_out += struct.pack('<B', x.voltage.value) + struct.pack('<B', x.enabled)
    raw_out += limewire_IP.packed + FC_IP.packed + BB1_IP.packed + BB2_IP.packed + BB3_IP.packed + FR_IP.packed

    crc = zlib.crc32(raw_out)

    raw_out += struct.pack('<I', crc)
    return raw_out
    
def send_eeprom_tftp(board: ipaddress.IPv4Address, content: bytes):
    print("Sending eeprom config over TFTP to " + str(board))
    tftp_client = tftpy.TftpClient(str(board))
    tftp_client.upload("eeprom.bin", BytesIO(content))

def configure_fc(PTs, TCs, VLVs, GSEIP, FCIP, BB1IP, BB2IP, BB3IP, FRIP, TFTPIP) -> tuple[bool, str]:
    try:
        eeprom_content = generate_fc_eeprom(PTs, TCs, VLVs, GSEIP, FCIP, BB1IP, BB2IP, BB3IP, FRIP)
        send_eeprom_tftp(TFTPIP, eeprom_content)
        return (True, "")
    except Exception as e:
        return (False, str(e))
    
def configure_bb(bb_num, PTs, TCs, VLVs, FCIP, BBIP, TFTPIP) -> tuple[bool, str]:
    try:
        eeprom_content = generate_bb_eeprom(bb_num, FCIP, BBIP, PTs, TCs, VLVs)
        send_eeprom_tftp(TFTPIP, eeprom_content)
        return (True, "")
    except Exception as e:
        return (False, str(e))
    
def configure_fr(FCIP, FRIP, TFTPIP) -> tuple[bool, str]:
    try:
        eeprom_content = generate_fr_eeprom(FCIP, FRIP)
        send_eeprom_tftp(TFTPIP, eeprom_content)
        return (True, "")
    except Exception as e:
        return (False, str(e))