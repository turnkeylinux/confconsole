# Copyright (c) 2009 Liraz Siri <liraz@turnkeylinux.org> - all rights reserved

import string
import struct
import socket
import math
from typing import Callable, Type, Union


def is_legal_ip(ip: str) -> bool:
    try:
        if len([octet for octet in ip.split(".")
                if 255 >= int(octet) >= 0]) != 4:
            return False
    except ValueError:
        return False

    try:
        packed = socket.inet_aton(ip)
    except socket.error:
        return False

    return True


AnyIP = Union[int, str, 'IP']


def _str2int(ip: str) -> int:
    bytes = list(map(int, ip.split('.')))
    out: int = struct.unpack("!L", struct.pack("BBBB", *bytes))[0]
    return out


def _int2str(num: int) -> str:
    bytes = struct.unpack("BBBB", struct.pack("!L", num))
    return '.'.join(list(map(str, bytes)))


class Error(Exception):
    pass


class IP(int):
    def __new__(cls: Type['IP'], arg: AnyIP) -> 'IP':
        if isinstance(arg, IP):
            return int.__new__(cls, int(arg))

        elif isinstance(arg, int):
            return int.__new__(cls, arg)

        else:
            if not is_legal_ip(arg):
                raise Error(f"illegal ip ({arg})")

            return int.__new__(cls, _str2int(arg))

    def __str__(self) -> str:
        return _int2str(self)

    def __repr__(self) -> str:
        return f"IP({str(self)})"

    def __add__(self, other: int) -> 'IP':
        return IP(int.__add__(self, other))

    def __sub__(self, other: int) -> 'IP':
        return IP(int.__sub__(self, other))

    def __and__(self, other: int) -> 'IP':
        return IP(int.__and__(self, other))

    def __or__(self, other: int) -> 'IP':
        return IP(int.__or__(self, other))

    def __xor__(self, other: int) -> 'IP':
        return IP(int.__xor__(self, other))


class IPRange:
    @classmethod
    def from_cidr(cls: Type['IPRange'], arg: str) -> 'IPRange':
        address, cidr = arg.split('/')
        netmask = 2 ** 32 - (2 ** (32 - int(cidr)))
        return cls(address, netmask)

    def __init__(self, ip: AnyIP, netmask: AnyIP):
        self.ip = IP(ip)
        self.netmask = IP(netmask)
        self.network = self.ip & self.netmask
        self.broadcast = self.network + 2 ** 32 - self.netmask - 1
        self.cidr = int(32 - math.log(2 ** 32 - self.netmask, 2))

    def __contains__(self, ip: AnyIP) -> bool:
        return self.network < IP(ip) < self.broadcast

    def __repr__(self) -> str:
        return f"IPRange('{self.ip}', '{self.netmask}')"

    def fmt_cidr(self) -> str:
        return f"{self.ip}/{self.cidr}"

    def __str__(self) -> str:
        return self.fmt_cidr()
