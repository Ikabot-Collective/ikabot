#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from ikabot.helpers.logging import getLogger
logger = getLogger(__name__)
import socket
import struct

from ikabot.config import *
from ikabot.helpers.process import run


def getDNSTXTRecordWithSocket(domain, DNS_server="8.8.8.8"):
    """Returns the TXT record from the DNS server for the given domain
    Parameters
    ----------
    domain : str
        Domain name
    DNS_server : str
        DNS server address, default is '8.8.8.8'
    Returns
    -------
    str
        TXT record
    """

    # DNS Query
    def build_query(domain):
        # Header Section
        ID = struct.pack(">H", 0x1234)  # Identifier: transaction ID
        FLAGS = struct.pack(">H", 0x0100)  # Standard query with recursion
        QDCOUNT = struct.pack(">H", 0x0001)  # One question
        ANCOUNT = struct.pack(">H", 0x0000)  # No answers
        NSCOUNT = struct.pack(">H", 0x0000)  # No authority records
        ARCOUNT = struct.pack(">H", 0x0000)  # No additional records
        header = ID + FLAGS + QDCOUNT + ANCOUNT + NSCOUNT + ARCOUNT

        # Question Section
        question = b""
        for part in domain.split("."):
            question += struct.pack("B", len(part)) + part.encode("utf-8")
        question += struct.pack("B", 0)  # End of string
        QTYPE = struct.pack(">H", 0x0010)  # TXT record
        QCLASS = struct.pack(">H", 0x0001)  # IN class
        question += QTYPE + QCLASS

        return header + question

    # Send DNS Query
    def send_query(query, server=DNS_server, port=53):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(5)
            sock.sendto(query, (server, port))
            data, _ = sock.recvfrom(512)  # 512 bytes is the max size of DNS datagram
            return data

    # Parse DNS Response
    def parse_response(response):
        # Skip the header
        header_size = 12
        offset = header_size

        # Read the question section
        while True:
            length = response[offset]
            if length == 0:
                break
            offset += length + 1
        offset += 5  # Skip the zero byte and QTYPE + QCLASS

        # Read the answer section
        while offset < len(response):
            # Read the name
            if response[offset] == 0xC0:
                offset += 2  # Pointer to a name
            else:
                # Name in the form of a sequence of labels
                while True:
                    length = response[offset]
                    if length == 0:
                        break
                    offset += length + 1
                offset += 1  # End of the name

            type = struct.unpack(">H", response[offset : offset + 2])[0]
            offset += 10  # Type (2 bytes) + Class (2 bytes) + TTL (4 bytes) + Data length (2 bytes)

            if type == 16:  # TXT record
                txt_length = struct.unpack(">H", response[offset - 2 : offset])[0]
                txt_data = response[offset : offset + txt_length]
                # TXT records can be split into multiple strings
                txt_strings = []
                while txt_data:
                    string_length = txt_data[0]
                    txt_strings.append(txt_data[1 : string_length + 1].decode("utf-8"))
                    txt_data = txt_data[string_length + 1 :]
                return " ".join(txt_strings)
            else:
                # Skip this record and move to the next
                data_length = struct.unpack(">H", response[offset - 2 : offset])[0]
                offset += data_length

        raise ValueError("No TXT record found")

    query = build_query(domain)
    response = send_query(query)
    return "http://" + parse_response(response)


def getDNSTXTRecordWithNSlookup(domain, DNS_server="8.8.8.8"):
    """Returns the TXT record from the DNS server for the given domain using the nslookup tool
    Parameters
    ----------
    domain : str
        Domain name
    DNS_server : str
        DNS server address, default is '8.8.8.8'
    Returns
    -------
    str
        TXT record
    """
    text = run(f"nslookup -q=txt {domain} {DNS_server}")
    parts = text.split('"')
    if len(parts) < 2:
        # the DNS output is not well formed
        raise Exception(
            f'The command "nslookup -q=txt {domain} {DNS_server}" returned bad data: {text}'
        )
    return "http://" + parts[1]


def getAddressWithSocket(domain):
    """Makes multiple attempts to obtain the ikabot public API server address with the socket library
    Returns
    -------
    str
        server address
    """
    try:
        return getDNSTXTRecordWithSocket(domain, "ns2.afraid.org")
    except Exception as e:
        logger.warning("Failed to obtain public API address from ns2.afraid.org, trying with 8.8.8.8: ", exc_info=True)
    try:
        return getDNSTXTRecordWithSocket(domain, "8.8.8.8")
    except Exception as e:
        logger.warning("Failed to obtain public API address from 8.8.8.8, trying with 1.1.1.1: ", exc_info=True)
    try:
        return getDNSTXTRecordWithSocket(domain, "1.1.1.1")
    except Exception as e:
        logger.warning("Failed to obtain public API address from 1.1.1.1: ", exc_info=True)
        raise e


def getAddressWithNSlookup(domain):
    """Makes multiple attempts to obtain the ikabot public API server address with the nslookup tool if it's installed
    Returns
    -------
    str
        server address
    """
    try:
        return getDNSTXTRecordWithNSlookup(domain, "ns2.afraid.org")
    except Exception as e:
        logger.warning("Failed to obtain public API address from ns2.afraid.org: ", exc_info=True)
    try:
        return getDNSTXTRecordWithNSlookup(domain, "")
    except Exception as e:
        logger.warning("Failed to obtain public API address from nslookup with system default DNS server: ", exc_info=True)
    try:
        return getDNSTXTRecordWithNSlookup(domain, "8.8.8.8")
    except Exception as e:
        logger.warning("Failed to obtain public API address from nslookup with 8.8.8.8: ", exc_info=True)
    try:
        return getDNSTXTRecordWithNSlookup(domain, "1.1.1.1")
    except Exception as e:
        logger.warning("Failed to obtain public API address from nslookup with 1.1.1.1: ", exc_info=True)
        raise e


def getAddress(domain="ikagod.twilightparadox.com"):
    """Makes multiple attempts to obtain the ikabot public API server address
    Parameters
    ----------
    domain : str
        Domain name
    Returns
    -------
    str
        server address
    """
    custom_address = os.getenv("CUSTOM_API_ADDRESS")
    if custom_address:
        return custom_address
    try:
        address = getAddressWithSocket(domain)
        assert "." in address or ":" in address.replace("http://", ""), (
            "Bad server address: " + address
        )
        return address.replace("/ikagod/ikabot", "")
    except Exception as e:
        logger.warning("Failed to obtain public API address from socket, falling back to nslookup: ", exc_info=True)
    try:
        address = getAddressWithNSlookup(domain)
        assert "." in address or ":" in address.replace("http://", ""), (
            "Bad server address: " + address
        )  # address is either hostname, IPv4 or IPv6
        return address.replace("/ikagod/ikabot", "")
    except Exception as e:
        logger.error("Failed to obtain public API address from both socket and nslookup: ", exc_info=True)
        raise e
