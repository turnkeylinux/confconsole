# Copyright (c) 2009 Liraz Siri <liraz@turnkeylinux.org> - all rights reserved

import string
import struct
import socket
import math


def is_legal_ip(ip):
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


def _str2int(ip):
    bytes = list(map(int, ip.split('.')))
    ip, = struct.unpack("!L", struct.pack("BBBB", *bytes))
    return ip


def _int2str(num):
    bytes = struct.unpack("BBBB", struct.pack("!L", num))
    return '.'.join(list(map(str, bytes)))


class Error(Exception):
    pass


class IP(int):
    def __new__(cls, arg):
        if isinstance(arg, IP):
            return int.__new__(cls, int(arg))

        elif isinstance(arg, int):
            return int.__new__(cls, arg)

        else:
            if not is_legal_ip(arg):
                raise Error("illegal ip (%s)" % arg)

            return int.__new__(cls, _str2int(arg))

    def __str__(self):
        return _int2str(self)

    def __repr__(self):
        return "IP(%r)" % str(self)

    @staticmethod
    def _numeric_method(method: str):
        def f(self, other: str):
            return IP(getattr(int, method)(self, other))

        return f

    __add__ = _numeric_method("__add__")
    __sub__ = _numeric_method("__sub__")
    __and__ = _numeric_method("__and__")
    __xor__ = _numeric_method("__xor__")
    __or__ = _numeric_method("__or__")


class IPRange:
    @classmethod
    def from_cidr(cls, arg):
        address, cidr = arg.split('/')
        netmask = 2 ** 32 - (2 ** (32 - int(cidr)))
        return cls(address, netmask)

    def __init__(self, ip, netmask):
        self.ip = IP(ip)
        self.netmask = IP(netmask)
        self.network = self.ip & self.netmask
        self.broadcast = self.network + 2 ** 32 - self.netmask - 1
        self.cidr = int(32 - math.log(2 ** 32 - self.netmask, 2))

    def __contains__(self, ip):
        return self.network < IP(ip) < self.broadcast

    def __repr__(self):
        return "IPRange('%s', '%s')" % (self.ip, self.netmask)

    def fmt_cidr(self):
        return "%s/%d" % (self.ip, self.cidr)

    __str__ = fmt_cidr
