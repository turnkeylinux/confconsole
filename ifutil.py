# Copyright (c) 2008 Alon Swartz <alon@turnkeylinux.org> - all rights reserved

import os
import re
import time
import fcntl
import socket

import executil

class Error(Exception):
    pass

SIOCGIFADDR = 0x8915
SIOCGIFNETMASK = 0x891b

class EtcNetworkInterfaces:
    """class for controlling /etc/network/interfaces

    An error will be raised if the interfaces file does not include the
    header: # UNCONFIGURED INTERFACES (in other words, we will not override
    any customizations)
    """

    CONF_FILE='/etc/network/interfaces'

    def __init__(self):
        self.read_conf()

    @staticmethod
    def _header():
        return "\n".join(["# UNCONFIGURED INTERFACES",
                          "# remove the above line if you edit this file"])

    @staticmethod
    def _loopback():
        return "\n".join(["auto lo",
                          "iface lo inet loopback"])

    def read_conf(self):
        self.conf = {}
        self.unconfigured = False

        for line in file(self.CONF_FILE).readlines():
            line = line.rstrip()

            if line == self._header().splitlines()[0]:
                self.unconfigured = True

            if not line or line.startswith("#"):
                continue

            if line.startswith("auto") or line.startswith("ifname"):
                ifname = line.split()[1]

            if not self.conf.has_key(ifname):
                self.conf[ifname] = line + "\n"
            else:
                self.conf[ifname] = self.conf[ifname] + line + "\n"

    def write_conf(self, ifname, ifconf):
        self.read_conf()
        if not self.unconfigured:
            raise Error("not writing to %s\nheader not found: %s" %
                        (self.CONF_FILE, self._header().splitlines()[0]))

        #append legal iface options already defined
        iface_opts = ('pre-up', 'up', 'post-up', 'pre-down', 'down', 'post-down')
        for line in self.conf[ifname].splitlines():
            line = line.strip()
            if line.split()[0] in iface_opts:
                ifconf.append("    " + line)

        fh = file(self.CONF_FILE, "w")
        print >> fh, self._header() + "\n"
        print >> fh, self._loopback() + "\n"
        print >> fh, "\n".join(ifconf) + "\n"

        for c in self.conf:
            if c in ('lo', ifname):
                continue

            print >> fh, self.conf[c]

        fh.close()

    def set_dhcp(self, ifname):
        ifconf = ["auto %s" % ifname,
                  "iface %s inet dhcp" % ifname]

        self.write_conf(ifname, ifconf)

    def set_manual(self, ifname):
        ifconf = ["auto %s" % ifname,
                  "iface %s inet manual" % ifname]

        self.write_conf(ifname, ifconf)

    def set_static(self, ifname, addr, netmask, gateway=None, nameservers=[]):
        ifconf = ["auto %s" % ifname,
                  "iface %s inet static" % ifname,
                  "    address %s" % addr,
                  "    netmask %s" % netmask]

        if gateway:
            ifconf.append("    gateway %s" % gateway)

        if nameservers:
            ifconf.append("    dns-nameservers %s" % " ".join(nameservers))

        self.write_conf(ifname, ifconf)

class EtcNetworkInterface:
    """enumerate interface information from /etc/network/interfaces"""

    def __init__(self, ifname):
        self.ifname = ifname

        interfaces = EtcNetworkInterfaces()

        self.conflines = []
        if ifname in interfaces.conf:
            self.conflines = interfaces.conf[ifname].splitlines()

    def _parse_attr(self, attr):
        for line in self.conflines:

            vals = line.strip().split()
            if not vals:
                continue

            if vals[0] == attr:
                return vals

        return []

    @property
    def method(self):
        try:
            return self._parse_attr('iface')[3]
        except IndexError:
            return

    @property
    def dns_nameservers(self):
        return self._parse_attr('dns-nameservers')[1:]

    def __getattr__(self, attrname):
        #attributes with multiple values will be returned in an array
        #exception: dns-nameservers always returns in array (expected)

        attrname = attrname.replace('_', '-')
        values = self._parse_attr(attrname)
        if len(values) > 2:
            return values[1:]
        elif len(values) > 1:
            return values[1]

        return

class NetInfo:
    """enumerate network related configurations"""

    def __init__(self, ifname):
        self.ifname = ifname
        self.ifreq = (self.ifname + '\0'*32)[:32]

    def _get_ioctl_addr(self, attrname):
        try:
            sockfd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            result = fcntl.ioctl(sockfd.fileno(), attrname, self.ifreq)
        except IOError:
            return None

        return socket.inet_ntoa(result[20:24])

    @property
    def addr(self):
        return self._get_ioctl_addr(SIOCGIFADDR)

    @property
    def netmask(self):
        return self._get_ioctl_addr(SIOCGIFNETMASK)

    @property
    def gateway(self):
        try:
            output = executil.getoutput("route -n")
        except executil.ExecError:
            return None

        for line in output.splitlines():
            m = re.search('^0.0.0.0\s+(.*?)\s+(.*)\s+%s' % self.ifname, line, re.M)
            if m:
                return m.group(1)

        return None

    @property
    def nameservers(self):
        def _parse_resolv(path):
            nameservers = []
            for line in file(path).readlines():
                if line.startswith('nameserver'):
                    nameservers.append(line.strip().split()[1])
            return nameservers

        #/etc/network/interfaces (static)
        interface = EtcNetworkInterface(self.ifname)
        if interface.dns_nameservers:
            return interface.dns_nameservers

        #resolvconf (dhcp)
        path = '/etc/resolvconf/run/interface'
        if os.path.exists(path):
            for f in os.listdir(path):
                if not f.startswith(self.ifname) or f.endswith('.inet'):
                    continue

                nameservers = _parse_resolv(os.path.join(path, f))
                if nameservers:
                    return nameservers

        #/etc/resolv.conf (fallback)
        nameservers = _parse_resolv('/etc/resolv.conf')
        if nameservers:
            return nameservers

        return []

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


def ifup(ifname):
    return executil.getoutput("ifup", ifname)

def ifdown(ifname):
    return executil.getoutput("ifdown", ifname)

def unconfigure_if(ifname):
    try:
        ifdown(ifname)
        interfaces = EtcNetworkInterfaces()
        interfaces.set_manual(ifname)
        executil.system("ifconfig %s 0.0.0.0" % ifname)
        ifup(ifname)
    except Exception, e:
        return str(e)

def set_static(ifname, addr, netmask, gateway, nameservers):
    try:
        ifdown(ifname)
        interfaces = EtcNetworkInterfaces()
        interfaces.set_static(ifname, addr, netmask, gateway, nameservers)
        output = ifup(ifname)

        net = NetInfo(ifname)
        if not net.addr:
            raise Error('Error obtaining IP address\n\n%s' % output)

    except Exception, e:
        return str(e)

def set_dhcp(ifname):
    try:
        ifdown(ifname)
        interfaces = EtcNetworkInterfaces()
        interfaces.set_dhcp(ifname)
        output = ifup(ifname)

        net = NetInfo(ifname)
        if not net.addr:
            raise Error('Error obtaining IP address\n\n%s' % output)

    except Exception, e:
        return str(e)

def get_ipconf(ifname):
    net = NetInfo(ifname)
    return net.addr, net.netmask, net.gateway, net.nameservers

def get_ifmethod(ifname):
    interface = EtcNetworkInterface(ifname)
    return interface.method

def get_ifnames():
    """ returns list of interface names (up and down) """
    ifnames = []
    for line in file('/proc/net/dev').readlines():
        try:
            ifname, junk = line.strip().split(":")
            ifnames.append(ifname)
        except ValueError:
            pass

    return ifnames

def get_hostname():
    return socket.gethostname()

def get_connections():
    connections = []
    for proto in ('tcp', 'tcp6', 'udp'):
        for line in file('/proc/net/' + proto).readlines()[1:]:
            conn = Connection(proto, line.split())
            connections.append(conn)

    return connections


