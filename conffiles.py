# Copyright (c) 2008 Alon Swartz <alon@turnkeylinux.org> - all rights reserved

import re

class Error(Exception):
    pass

class Interfaces:
    """class for controlling /etc/network/interfaces

    An error will be raised if the interfaces file does not include the
    header: # UNCONFIGURED INTERFACES (in other words, we will not override
    any customizations)
    """

    CONF_FILE='/etc/network/interfaces'

    def load_conf(self):
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

    def __init__(self):
        self.load_conf()
        if not self.unconfigured:
            raise Error("%s is not \'unconfigured\'" % self.CONF_FILE)

    @staticmethod
    def _header():
        return "\n".join(["# UNCONFIGURED INTERFACES",
                          "# remove the above line if you edit this file"])

    @staticmethod
    def _loopback():
        return "\n".join(["auto lo",
                          "iface lo inet loopback"])

    def write_conf(self, ifname, ifconf):
        self.load_conf()

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

    def set_staticip(self, ifname, addr, netmask, gateway=None):
        ifconf = ["auto %s" % ifname,
                  "iface %s inet static" % ifname,
                  "    address %s" % addr,
                  "    netmask %s" % netmask]

        if gateway:
            ifconf.append("    gateway %s" % gateway)

        self.write_conf(ifname, ifconf)

