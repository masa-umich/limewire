import ipaddress
from nicegui import run

from loguru import logger
from scapy.all import IP, UDP, send
from scapy.interfaces import get_working_ifaces
from scapy.layers.ntp import NTPHeader


async def send_all():
    await run.cpu_bound(send_ntp, ipaddress.IPv4Network("0.0.0.0/0"), True)

def send_ntp(network: ipaddress.IPv4Network, all_iface: bool):
    logger.info("Broadcasting NTP")
    if all_iface:
        broadcast_strs = []
        for iface in get_working_ifaces():
            if iface.ip is not None and iface.ip.strip() != "":
                broadcast_strs.append(f"{network.broadcast_address}%{iface.name}")
    else:
        broadcast_strs = [str(network.broadcast_address)]
    
    for b in broadcast_strs:
        ntp_packet = NTPHeader(mode = 5)
        send(IP(dst=b)/UDP(dport=123)/ntp_packet)
