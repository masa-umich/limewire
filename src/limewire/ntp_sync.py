from scapy.all import IP, UDP, send
from scapy.error import Scapy_Exception
from scapy.layers.ntp import NTPHeader


def send_ntp_sync(logger=None):
    if logger is not None:
        logger.info("Sending NTP sync.")

    ntp_packet = NTPHeader(mode=5)
    packet = IP(dst="141.212.192.255") / UDP(dport=123) / ntp_packet

    try:
        send(packet)
    except Scapy_Exception:
        if logger is not None:
            logger.warning("NTP sync failed.")
