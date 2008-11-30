# Copyright (c) 2008 Alon Swartz <alon@turnkeylinux.org> - all rights reserved

import re
import time
import fcntl
import struct
import socket

import executil

SIOCGIFADDR = 0x8915
SIOCGIFNETMASK = 0x891b
SIOCGIFBRDADDR = 0x8919

def _readfile(path):
    fh = file(path)
    lines = fh.readlines()
    fh.close()
    return lines

class NIC:
    """class to control a network interface cards configuration"""

    class ATTRIBS:
        ADDRS = {
            'addr':         SIOCGIFADDR,
            'netmask':      SIOCGIFNETMASK,
            'brdaddr':      SIOCGIFBRDADDR,
        }

    def __init__(self, ifname):
        self.ifname = ifname
        self.ifreq = (self.ifname + '\0'*32)[:32]

    def _get_addr(self, attrname):
        try:
            sockfd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            result = fcntl.ioctl(sockfd.fileno(), attrname, self.ifreq)
        except IOError:
            return None

        return socket.inet_ntoa(result[20:24])

    def set_ipaddr(self, addr):
        if addr == self.addr or addr == "":
            return

        executil.system("ifconfig %s %s up" % (self.ifname, addr))

    def set_netmask(self, netmask):
        if netmask == self.netmask or netmask == "":
            return

        executil.system("ifconfig %s netmask %s" % (self.ifname, netmask))

    def __getattr__(self, attrname):
        if attrname in self.ATTRIBS.ADDRS:
            return self._get_addr(self.ATTRIBS.ADDRS[attrname])

class Netconf(NIC):
    """class to extend the NIC class with network related configurations
    not directly related to the interface itself
    """

    def set_staticip(self, addr, netmask):
        self.set_ipaddr(addr)
        self.set_netmask(netmask)
        Interfaces(self.ifname).set_staticip(addr, netmask)

    def get_dhcp(self):
        executil.getoutput("udhcpc --now --quit --interface %s" % IFNAME)
        Interfaces(self.ifname).set_dhcp()

    @staticmethod
    def get_gateway():
        output = executil.getoutput("route -n")
        m = re.search('^0.0.0.0\s+(.*?)\s', output, re.M)
        if m:
            return m.group(1)
        return None

    def set_gateway(self, gateway):
        if gateway == self.gateway or gateway == "":
            return

        if self.gateway:
            executil.system("route del default gw %s" % self.gateway)

        for i in range(3):
            try:
                executil.system("route add default gw %s" % gateway)
                break
            except:
                time.sleep(1)

    @staticmethod
    def get_nameserver():
        for line in _readfile('/etc/resolv.conf'):
            if line.startswith('nameserver'):
                try:
                    junk, nameserver = line.strip().split()
                    return nameserver
                except:
                    pass
        return None

    def set_nameserver(self, nameserver):
        if self.nameserver == nameserver:
            return

        fh = file('/etc/resolv.conf', "w")
        print >> fh, "nameserver %s" % nameserver
        fh.close()

    def __getattr__(self, attrname):
        if attrname in self.ATTRIBS.ADDRS:
            return self._get_addr(self.ATTRIBS.ADDRS[attrname])

        if attrname == "gateway":
            return self.get_gateway()

        if attrname == "nameserver":
            return self.get_nameserver()

class InterfacesError(Exception):
    pass

class Interfaces:
    """class for controlling /etc/network/interfaces

    an error will be raised if the interfaces file does not include the
    header: # UNCONFIGURED INTERFACES (in other words, we will not override
    any customizations)
    """

    def __init__(self, ifname):
        self.ifname = ifname
        self.path = '/etc/network/interfaces'

        if not self._is_unconfigured():
            raise InterfacesError("%s is not \'unconfigured\'" % self.path)

    @staticmethod
    def _header():
        return "\n".join(["# UNCONFIGURED INTERFACES",
                          "# remove the above line if you edit this file"])

    @staticmethod
    def _loopback():
        return "\n".join(["auto lo",
                          "iface lo inet loopback"])

    def _is_unconfigured(self):
        for line in _readfile(self.path):
            if line.strip() == self._header().splitlines()[0]:
                return True

        return False

    def set_dhcp(self):
        fh = file(self.path, "w")
        print >> fh, self._header() + "\n"
        print >> fh, self._loopback() + "\n"
        print >> fh, "auto %s" % self.ifname
        print >> fh, "iface %s inet dhcp" % self.ifname
        fh.close()

    def set_staticip(self, addr, netmask, gateway):
        fh = file(self.path, "w")
        print >> fh, self._header() + "\n"
        print >> fh, self._loopback() + "\n"
        print >> fh, "auto %s" % self.ifname
        print >> fh, "iface %s inet static" % self.ifname
        print >> fh, "    address %s" % addr
        print >> fh, "    netmask %s" % netmask
        print >> fh, "    gateway %s" % gateway
        fh.close()

class Connection:
    """class for holding a network connections configuration"""

    def __init__(self, proto, attribs, debug=False):
        """
        proto is one of tcp, tcp6, udp
        attribs is a line from /proc/net/$proto (split into an array) 
        """
        self.proto = proto
        self.lhost, self.lport = self._map_hostport(attribs[1])
        self.rhost, self.rport = self._map_hostport(attribs[2])

        self.status = self._map_status(attribs[3])

        if debug:
            print "%s\t%s:%s\t\t%s:%s\t\t%s" % (self.proto, self.lhost, self.lport,
                                                self.rhost, self.rport, self.status)

    @staticmethod
    def _int2host(host):
        return ".".join(map(str, ((host >> 0) & 0xff, (host >> 8) & 0xff,
                                  (host >> 16) & 0xff, (host >> 24) & 0xff)))

    @classmethod
    def _map_hostport(cls, attrib):
        host, port = attrib.split(":", 1)
        host = cls._int2host(int(host, 16))
        port = int(port, 16)

        return host, port

    @staticmethod
    def _map_status(attrib):
        status = {'01': 'ESTABLISHED',
                  '0A': 'LISTENING',
                  '10': 'WAITING'}
        try:
            return status[attrib]
        except KeyError:
            return 'UNKNOWN'

def valid_ipv4(addr):
    ip4_re = re.compile(r'^(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}$') 
    if not ip4_re.search(addr):
        return False
    return True

# convenience functions

IFNAME = 'eth0'  # todo: get preferred interface (ifprobe)
def set_ipconf(addr, netmask, gateway, nameserver):
    net = Netconf(IFNAME)
    net.set_gateway(gateway)
    net.set_nameserver(nameserver)
    try:
        net.set_staticip(addr, netmask, gateway)
    except InterfacesError, e:
        return str(e)

def get_ipconf():
    net = Netconf(IFNAME)
    return net.addr, net.netmask, net.gateway, net.nameserver

def get_dhcp():
    net = Netconf(IFNAME)
    try:
        net.get_dhcp()
    except executil.ExecError, e:
        return str(e)
    except InterfacesError, e:
        return str(e)

def get_hostname():
    return socket.gethostname()

def get_connections():
    connections = []
    for proto in ('tcp', 'tcp6', 'udp'):
        lines = _readfile('/proc/net/' + proto)
        for line in lines[1:]:
            conn = Connection(proto, line.split())
            connections.append(conn)

    return connections


