# Copyright (c) 2008 Alon Swartz <alon@turnkeylinux.org> - all rights reserved
# Copyright (c) 2022 TurnKey GNU/Linux <admin@turnkeylinux.org>

import os
from time import sleep
import subprocess
from typing import Optional

from netinfo import InterfaceInfo
from netinfo import get_hostname


class IfError(Exception):
    pass


class EtcNetworkInterfaces:
    """class for controlling /etc/network/interfaces

    An error will be raised if the interfaces file does not include the
    header: # UNCONFIGURED INTERFACES (in other words, we will not override
    any customizations)
    """

    CONF_FILE = '/etc/network/interfaces'
    HEADER_UNCONFIGURED = "# UNCONFIGURED INTERFACES"

    def __init__(self):
        self.read_conf()

    def read_conf(self) -> None:
        self.conf: dict[str, str] = {}
        self.unconfigured = False

        ifname = None
        with open(self.CONF_FILE) as fob:
            for line in fob:
                line = line.rstrip()

                if line == self.HEADER_UNCONFIGURED:
                    self.unconfigured = True

                if not line or line.startswith("#"):
                    continue

                if line.startswith("auto") or line.startswith("allow-hotplug"):
                    ifname = line.split()[1]
                    self.conf[ifname] = line + "\n"
                elif ifname:
                    self.conf[ifname] += line + "\n"

    def _get_iface_opts(self, ifname: str) -> list[str]:
        iface_opts = ('pre-up', 'up', 'post-up',
                      'pre-down', 'down', 'post-down')
        if ifname not in self.conf:
            return []

        ifconf = self.conf[ifname]
        return [line.strip()
                for line in ifconf.splitlines()
                if line.strip().split()[0] in iface_opts]

    def _get_bridge_opts(self, ifname: str) -> list:
        bridge_opts = ('bridge_ports', 'bridge_ageing', 'bridge_bridgeprio',
                       'bridge_fd', 'bridge_gcinit', 'bridge_hello',
                       'bridge_hw', 'bridge_maxage', 'bridge_maxwait',
                       'bridge_pathcost', 'bridge_portprio', 'bridge_stp',
                       'bridge_waitport')
        if ifname not in self.conf:
            return []

        ifconf = self.conf[ifname]
        return [line.strip()
                for line in ifconf.splitlines()
                if line.strip().split()[0] in bridge_opts]

    def write_conf(self, ifname: str, ifconf: str) -> None:
        self.read_conf()
        if not self.unconfigured:
            raise IfError(f"refusing to write to {self.CONF_FILE}\n"
                          f"header not found: {self.HEADER_UNCONFIGURED}")

        # carry over previously defined bridge options
        ifconf += "\n" + "\n".join(["    " + opt
                                   for opt in self._get_bridge_opts(ifname)])

        # carry over previously defined interface options
        ifconf += "\n" + "\n".join(["    " + opt
                                    for opt in self._get_iface_opts(ifname)])

        with open(self.CONF_FILE, "w") as fob:
            fob.write(self.HEADER_UNCONFIGURED+'\n')
            fob.write("# remove the above line if you edit this file")

            for iface in self.conf.keys():
                if iface:
                    fob.write('\n\n')
                    if iface == ifname:
                        fob.writelines(ifconf.rstrip())
                    else:
                        fob.writelines(self.conf[iface].rstrip())
            fob.write('\n')

    @staticmethod
    def _preproc_if(ifname_conf: str) -> list[str]:
        lines = ifname_conf.splitlines()
        if len(lines) == 2:
            return lines
        new_lines = []
        hostname = get_hostname()
        for line in lines:
            _line = line.lstrip()
            if (_line.startswith('allow-hotplug')
                    or _line.startswith('auto')
                    or _line.startswith('iface')
                    or _line.startswith('wpa-conf')):
                new_lines.append(line)
            elif _line.startswith('hostname'):
                if hostname:
                    new_lines.append(f'    hostname {hostname}')
                else:
                    continue
            elif (_line.startswith('address')
                    or _line.startswith('netmask')
                    or _line.startswith('gateway')
                    or _line.startswith('dns-nameserver')):
                continue
            else:
                raise IfError(f'Unexpected config line: {line}')
        return new_lines

    def set_dhcp(self, ifname: str) -> None:
        ifconf = self._preproc_if(self.conf[ifname])
        ifconf[1] = f'iface {ifname} inet dhcp'

        ifconf_str = "\n".join(ifconf)
        self.write_conf(ifname, ifconf_str)

    def set_manual(self, ifname: str) -> None:
        ifconf = self._preproc_if(self.conf[ifname])
        ifconf[1] = f'iface {ifname} inet manual'
        ifconf_str = "\n".join(ifconf)
        self.write_conf(ifname, ifconf_str)

    def set_static(self, ifname: str, addr: str, netmask: str,
                   gateway: str = None, nameservers: list = None
                   ) -> None:
        ifconf = self._preproc_if(self.conf[ifname])
        ifconf[1] = f'iface {ifname} inet static'

        ifconf.extend([f"    address {addr}",
                       f"    netmask {netmask}"])
        if gateway:
            ifconf.append(f"    gateway {gateway}")
        if nameservers:
            ifconf.append(f"    dns-nameservers {' '.join(nameservers)}")

        ifconf_str = "\n".join(ifconf)
        self.write_conf(ifname, ifconf_str)


class EtcNetworkInterface:
    """enumerate interface information from /etc/network/interfaces"""

    def __init__(self, ifname: str):
        self.ifname = ifname

        interfaces = EtcNetworkInterfaces()

        self.conflines = []
        if ifname in interfaces.conf:
            self.conflines = interfaces.conf[ifname].splitlines()

    def _parse_attr(self, attr: str) -> list[str]:
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

    def __getattr__(self, attrname: str) -> list[str]:
        # attributes with multiple values will be returned in an array
        # exception: dns-nameservers always returns in array (expected)

        attrname = attrname.replace('_', '-')
        values = self._parse_attr(attrname)
        if len(values) > 2:
            return values[1:]
        elif len(values) > 1:
            return [values[1]]

        return []


def get_nameservers(ifname: str) -> list[str]:

    # /etc/network/interfaces (static)
    interface = EtcNetworkInterface(ifname)
    if interface.dns_nameservers:
        return interface.dns_nameservers

    def parse_resolv(path: str) -> list[str]:
        nameservers = []
        with open(path, 'r') as fob:
            for line in fob:
                if line.startswith('nameserver'):
                    nameservers.append(line.strip().split()[1])
        return nameservers

    # resolvconf (dhcp)
    path = '/etc/resolvconf/run/interface'
    if os.path.exists(path):
        for f in os.listdir(path):
            if not f.startswith(ifname) or f.endswith('.inet'):
                continue

            nameservers = parse_resolv(os.path.join(path, f))
            if nameservers:
                return nameservers

    # /etc/resolv.conf (fallback)
    nameservers = parse_resolv('/etc/resolv.conf')
    if nameservers:
        return nameservers

    return []


def ifup(ifname: str) -> str:
    return subprocess.check_output(["ip", "link", "set", ifname, "up"],
                                   capture_output=True, text=True)


def ifdown(ifname: str) -> str:
    return subprocess.run(["ip", "link", "set", ifname, "down"])


def unconfigure_if(ifname: str) -> Optional[str]:
    try:
        ifdown(ifname)
        interfaces = EtcNetworkInterfaces()
        interfaces.set_manual(ifname)
        subprocess.check_output(['ifconfig', ifname, '0.0.0.0'])
        ifup(ifname)
        return None
    except subprocess.CalledProcessError as e:
        return str(e)


def set_static(ifname: str, addr: str, netmask: str,
               gateway: str, nameservers: list[str]
               ) -> Optional[str]:
    try:
        ifdown(ifname)
        interfaces = EtcNetworkInterfaces()
        interfaces.set_static(ifname, addr, netmask, gateway, nameservers)

        # FIXME when issue in ifupdown/virtio-net becomes apparent
        sleep(0.5)

        output = ifup(ifname)

        net = InterfaceInfo(ifname)
        if not net.addr:
            raise IfError(f'Error obtaining IP address\n\n{output}')
        return None
    except Exception as e:
        return str(e)


def set_dhcp(ifname: str) -> Optional[str]:
    try:
        ifdown(ifname)
        interfaces = EtcNetworkInterfaces()
        interfaces.set_dhcp(ifname)
        output = ifup(ifname)

        net = InterfaceInfo(ifname)
        if not net.addr:
            raise IfError(f'Error obtaining IP address\n\n{output}')
        return None
    except Exception as e:
        return str(e)


def get_ipconf(ifname: str, error: bool = False
               ) -> tuple[str, str, str, list[str]]:
    net = InterfaceInfo(ifname)
    return (net.addr, net.netmask, net.get_gateway(error),
            get_nameservers(ifname))


def get_ifmethod(ifname: str) -> str:
    interface = EtcNetworkInterface(ifname)
    return interface.method
