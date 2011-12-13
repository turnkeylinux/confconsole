# Copyright (c) 2008 Alon Swartz <alon@turnkeylinux.org> - all rights reserved

import os
import re

import executil
from netinfo import InterfaceInfo

class Error(Exception):
    pass

class EtcNetworkInterfaces:
    """class for controlling /etc/network/interfaces

    An error will be raised if the interfaces file does not include the
    header: # UNCONFIGURED INTERFACES (in other words, we will not override
    any customizations)
    """

    CONF_FILE='/etc/network/interfaces'
    HEADER_UNCONFIGURED = "# UNCONFIGURED INTERFACES"

    def __init__(self):
        self.read_conf()

    def read_conf(self):
        self.conf = {}
        self.unconfigured = False

        ifname = None
        for line in file(self.CONF_FILE).readlines():
            line = line.rstrip()

            if line == self.HEADER_UNCONFIGURED:
                self.unconfigured = True

            if not line or line.startswith("#"):
                continue

            if line.startswith("auto") or line.startswith("iface"):
                ifname = line.split()[1]
                self.conf[ifname] = line + "\n"
            elif ifname:
                self.conf[ifname] += line + "\n"

    def _get_iface_opts(self, ifname):
        iface_opts = ('pre-up', 'up', 'post-up', 'pre-down', 'down', 'post-down')
        if ifname not in self.conf:
            return []

        ifconf = self.conf[ifname]
        return [ line.strip()
                 for line in ifconf.splitlines() 
                 if line.strip().split()[0] in iface_opts ]

    def write_conf(self, ifname, ifconf):
        self.read_conf()
        if not self.unconfigured:
            raise Error("refusing to write to %s\nheader not found: %s" %
                        (self.CONF_FILE, self.HEADER_UNCONFIGURED))

        # carry over previously defined interface options
        ifconf += "\n" + "\n".join([ "    " + opt 
                                   for opt in self._get_iface_opts(ifname) ])

        fh = file(self.CONF_FILE, "w")
        print >> fh, self.HEADER_UNCONFIGURED
        print >> fh, "# remove the above line if you edit this file"
        print >> fh
        print >> fh, "auto lo"
        print >> fh, "iface lo inet loopback"
        print >> fh

        print >> fh, ifconf + "\n"

        for c in self.conf:
            if c in ('lo', ifname):
                continue

            print >> fh, self.conf[c]

        fh.close()

    def set_dhcp(self, ifname):
        ifconf = "auto %s\niface %s inet dhcp" % (ifname, ifname)
        self.write_conf(ifname, ifconf)

    def set_manual(self, ifname):
        ifconf = "auto %s\niface %s inet manual" % (ifname, ifname)
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

        ifconf = "\n".join(ifconf)
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

def get_nameservers(ifname):
    #/etc/network/interfaces (static)
    interface = EtcNetworkInterface(ifname)
    if interface.dns_nameservers:
        return interface.dns_nameservers

    def parse_resolv(path):
        nameservers = []
        for line in file(path).readlines():
            if line.startswith('nameserver'):
                nameservers.append(line.strip().split()[1])
        return nameservers

    #resolvconf (dhcp)
    path = '/etc/resolvconf/run/interface'
    if os.path.exists(path):
        for f in os.listdir(path):
            if not f.startswith(ifname) or f.endswith('.inet'):
                continue

            nameservers = parse_resolv(os.path.join(path, f))
            if nameservers:
                return nameservers

    #/etc/resolv.conf (fallback)
    nameservers = parse_resolv('/etc/resolv.conf')
    if nameservers:
        return nameservers

    return []


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

        net = InterfaceInfo(ifname)
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

        net = InterfaceInfo(ifname)
        if not net.addr:
            raise Error('Error obtaining IP address\n\n%s' % output)

    except Exception, e:
        return str(e)

def get_ipconf(ifname):
    net = InterfaceInfo(ifname)
    return net.addr, net.netmask, net.gateway, get_nameservers(ifname)

def get_ifmethod(ifname):
    interface = EtcNetworkInterface(ifname)
    return interface.method

