from scapy.all import IP, UDP, send
from scapy.layers.ntp import NTPHeader


def send_ntp_sync():
    ntp_packet = NTPHeader(mode=5)
    packet = IP(dst="141.212.192.255") / UDP(dport=123) / ntp_packet
    send(packet)
