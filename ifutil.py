# Copyright (c) 2008 Alon Swartz <alon@turnkeylinux.org> - all rights reserved

import os
import re
import time
import fcntl
import struct
import socket

import executil
import conffiles

SIOCGIFADDR = 0x8915
SIOCGIFNETMASK = 0x891b
SIOCGIFBRDADDR = 0x8919

def _readfile(path):
    fh = file(path)
    lines = fh.readlines()
    fh.close()
    return lines

class Error(Exception):
    pass

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
        if addr == self.addr:
            return

        if not addr:
            raise Error("No IP address provided")

        if not is_ipaddr(addr):
            raise Error("Invalid IP address: %s" % addr)

        executil.system("ifconfig %s %s up" % (self.ifname, addr))

    def set_netmask(self, netmask):
        if netmask == self.netmask:
            return

        if not netmask:
            raise Error("No netmask provided")

        if not is_ipaddr(netmask):
            raise Error("Invalid netmask: %s" % netmask)

        executil.system("ifconfig %s netmask %s" % (self.ifname, netmask))

    def __getattr__(self, attrname):
        if attrname in self.ATTRIBS.ADDRS:
            return self._get_addr(self.ATTRIBS.ADDRS[attrname])

class Netconf(NIC):
    """class to extend the NIC class with network related configurations
    not directly related to the interface itself
    """

    def set_staticip(self, addr, netmask, gateway):
        self.set_ipaddr(addr)
        self.set_netmask(netmask)
        if gateway:
            self.set_gateway(gateway)
        else:
            self.del_gateway()

        interfaces = conffiles.Interfaces()
        interfaces.set_staticip(self.ifname, addr, netmask, gateway)

    def get_dhcp(self):
        executil.getoutput("udhcpc --now --quit --interface %s" % self.ifname)
        interfaces = conffiles.Interfaces()
        interfaces.set_dhcp(self.ifname)

    def get_gateway(self):
        try:
            output = executil.getoutput("route -n")
        except executil.ExecError:
            return None

        for line in output.splitlines():
            m = re.search('^0.0.0.0\s+(.*?)\s+(.*)\s+%s' % self.ifname, line, re.M)
            if m:
                return m.group(1)

        return None

    def del_gateway(self):
        if self.gateway:
            executil.system("route del default gw %s" % self.gateway)

    def set_gateway(self, gateway):
        def _set_gateway(gateway):
            try:
                executil.system("route add default gw %s" % gateway)
            except executil.ExecError:
                return False
            return True

        if gateway == self.gateway:
            return

        if not is_ipaddr(gateway):
            raise Error("Invalid gateway: %s" % gateway)

        self.del_gateway()
        
        for i in range(3):
            if _set_gateway(gateway):
                return

            time.sleep(1)

        raise Error("Unable to configure gateway: %s" % gateway)

    def get_nameserver(self):
        conf = '/var/run/resolvconf/interface/%s.udhcpc' % self.ifname
        if os.path.exists(conf):
            for line in _readfile(conf):
                if line.startswith('nameserver'):
                    try:
                        junk, nameserver = line.strip().split()
                        return nameserver
                    except:
                        pass
        return None

    def del_nameserver(self):
        if self.nameserver:
            executil.system("resolvconf -d %s.udhcpc" % self.ifname)

    def set_nameserver(self, nameserver):
        if self.nameserver == nameserver:
            return

        if not is_ipaddr(nameserver):
            raise Error("Invalid nameserver: %s" % nameserver)

        executil.system("echo nameserver %s | \
                        resolvconf -a %s.udhcpc" % (nameserver, self.ifname))

    def __getattr__(self, attrname):
        if attrname in self.ATTRIBS.ADDRS:
            return self._get_addr(self.ATTRIBS.ADDRS[attrname])

        if attrname == "gateway":
            return self.get_gateway()

        if attrname == "nameserver":
            return self.get_nameserver()

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


def is_ipaddr(ip):
    ipv4 = '^(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}$'
    if not re.match(ipv4, ip):
        return False

    try:
        packed = socket.inet_aton(ip)
    except socket.error:
        return False

    return True

def get_ifmethod(ifname):
    conf = conffiles.Interfaces().conf
    if not conf.has_key(ifname):
        return None

    m = re.match(".*\niface %s inet (.*)" % ifname, conf[ifname])
    if m:
        return m.group(1)

    return None

def get_ifnames():
    """ returns list of interface names (up and down) """
    ifnames = []
    for line in _readfile('/proc/net/dev'):
        try:
            ifname, junk = line.strip().split(":")
            ifnames.append(ifname)
        except ValueError:
            pass

    return ifnames

def set_ipconf(ifname, addr, netmask, gateway, nameserver):
    net = Netconf(ifname)
    try:
        net.set_staticip(addr, netmask, gateway)
        if nameserver:
            net.set_nameserver(nameserver)
        else:
            net.del_nameserver()
    except Error, e:
        return str(e)
    except executil.ExecError, e:
        return str(e)
    except conffiles.Error, e:
        return str(e)

def get_ipconf(ifname):
    net = Netconf(ifname)
    return net.addr, net.netmask, net.gateway, net.nameserver

def get_dhcp(ifname):
    net = Netconf(ifname)
    try:
        net.get_dhcp()
    except Error, e:
        return str(e)
    except executil.ExecError, e:
        return str(e)
    except conffiles.Error, e:
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


