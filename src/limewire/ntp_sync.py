from scapy.all import IP, UDP, send
from scapy.layers.ntp import NTPHeader


def send_ntp_sync(fc_ip_addr: str):
    ntp_packet = NTPHeader(mode=5)
    packet = IP(dst=fc_ip_addr) / UDP(dport=123) / ntp_packet
    send(packet)
