from dataclasses import dataclass, field
import subprocess
from time import sleep
import os
import re

from netinfo import InterfaceInfo
from netinfo import get_hostname


class IfError(Exception):
    pass


class InvalidIPv4Error(IfError):
    pass


class ManuallyConfiguredError(IfError):
    pass


class InterfaceNotFoundError(IfError):
    pass


class BadIfConfigError(IfError):
    pass


IPV4_RE = r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(.*)$"
IPV4_CIDR = r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})/(\d{1,2})(.*)$"


def _preprocess_interface_config(config: str) -> list[str]:
    """Process and Validate Networking Interface"""
    lines = config.splitlines()
    new_lines = []
    hostname = get_hostname()

    for line in lines:
        _line = line.strip()

        if _line.startswith(("allow-hotplug", "auto", "iface", "wpa-conf")):
            new_lines.append(line)
        elif _line.startswith("hostname"):
            if hostname:
                new_lines.append(f"    hostname {hostname}")
            else:
                continue
        elif _line.startswith("post-up"):
            new_lines.append(f"    {_line}")
        elif _line.startswith(
            ("address", "netmask", "gateway", "dns-nameserver")
        ):
            continue
        else:
            raise BadIfConfigError(f"Unexpected config line: {line}")
    if len(new_lines) == 2 and hostname:
        new_lines.append(f"    hostname {hostname}")
    return new_lines


@dataclass
class IPv4:
    p0: int
    p1: int
    p2: int
    p3: int

    @classmethod
    def parse(cls, value: str) -> "IPv4":
        matches = re.match(IPV4_RE, value.strip())
        if not matches:
            raise InvalidIPv4Error(f"{value!r} is not a valid IPv4")
        if matches.group(5):
            raise InvalidIPv4Error(
                f"{value!r} is not a valid IPv4 (junk after ip segments)"
            )

        ip = cls(
            int(matches.group(1)),
            int(matches.group(2)),
            int(matches.group(3)),
            int(matches.group(4)),
        )

        if ip.p0 < 0 or ip.p0 > 255:
            raise InvalidIPv4Error(
                f"{value!r} is not a valid IPv4 ({ip.p0} not in range 0-255"
            )
        if ip.p1 < 0 or ip.p1 > 255:
            raise InvalidIPv4Error(
                f"{value!r} is not a valid IPv4 ({ip.p1} not in range 0-255"
            )
        if ip.p2 < 0 or ip.p2 > 255:
            raise InvalidIPv4Error(
                f"{value!r} is not a valid IPv4 ({ip.p2} not in range 0-255"
            )
        if ip.p3 < 0 or ip.p3 > 255:
            raise InvalidIPv4Error(
                f"{value!r} is not a valid IPv4 ({ip.p3} not in range 0-255"
            )
        return ip

    def __str__(self) -> str:
        return f"{self.p0}.{self.p1}.{self.p2}.{self.p3}"


class NetworkInterfaces:
    HEADER_UNCONFIGURED = "# UNCONFIGURED INTERFACES"
    CONF_FILE = "/etc/network/interfaces"

    conf: dict[str, list[str]] = {}
    unconfigured: bool = True

    _iface_opts = ["pre-up", "up", "post-up", "pre-down", "down", "post-down"]

    _bridge_opts = [
        "bridge_ports",
        "bridge_ageing",
        "bridge_bridgeprio",
        "bridge_fd",
        "bridge_gcinit",
        "bridge_hello",
        "bridge_hw",
        "bridge_maxage",
        "bridge_maxwait",
        "bridge_pathcost",
        "bridge_portprio",
        "bridge_stp",
        "bridge_waitport",
    ]

    def _get_opts_subset(self, ifname: str, opts: list[str]) -> list[str]:
        if ifname not in self.conf:
            raise InterfaceNotFoundError(f"no existing config for {ifname}")
        return [
            line.strip()
            for line in self.conf[ifname]
            if line.strip().split()[0] in opts
        ]

    def get_iface_opts(self, ifname: str) -> list[str]:
        return self._get_opts_subset(ifname, self._iface_opts)

    def get_bridge_opts(self, ifname: str) -> list[str]:
        return self._get_opts_subset(ifname, self._bridge_opts)

    def duplicate(self) -> "NetworkInterfaces":
        interfaces = NetworkInterfaces()
        interfaces.unconfigured = self.unconfigured
        interfaces.conf = {
            key: [i for i in value] for key, value in self.conf.items()
        }
        return interfaces

    def read(self) -> None:
        # clear config
        self.conf = {}
        self.unconfigured = False

        ifname: str | None = None

        with open(self.CONF_FILE) as fob:
            for line in fob:
                line = line.rstrip()

                if line == self.HEADER_UNCONFIGURED:
                    self.unconfigured = True

                if not line or line.startswith("#"):
                    continue

                if line.startswith("auto") or line.startswith("allow-hotplug"):
                    ifname = line.split()[1]
                    self.conf[ifname] = [line]
                elif ifname:
                    self.conf[ifname].append(line)

    def write(self) -> None:
        if not self.unconfigured:
            raise ManuallyConfiguredError(
                f"refusing to write to {self.CONF_FILE}\n"
                f"header not found: {self.HEADER_UNCONFIGURED}"
            )

        with open(self.CONF_FILE, "w") as fob:
            fob.write(self.HEADER_UNCONFIGURED + "\n")
            for iface in self.conf.keys():
                fob.write("\n\n")
                fob.write("\n".join(self.conf[iface]))
                fob.write("\n")

    def gen_default_if_config(self, ifname: str) -> None:
        if ifname.startswith("e"):
            self.conf[ifname] = _preprocess_interface_config(
                f"auto {ifname}\niface {ifname} inet dhcp"
            )
        else:
            raise InterfaceNotFoundError(f"no existing config for {ifname}")

    def set_dhcp(self, ifname: str) -> None:
        if ifname not in self.conf:
            self.gen_default_if_config(ifname)

        ifconf = _preprocess_interface_config("\n".join(self.conf[ifname]))
        ifconf[1] = f"iface {ifname} inet dhcp"
        self.conf[ifname] = ifconf

        self.write()

    def set_manual(self, ifname: str) -> None:
        if ifname not in self.conf:
            self.gen_default_if_config(ifname)

        ifconf = _preprocess_interface_config("\n".join(self.conf[ifname]))
        ifconf[1] = f"iface {ifname} inet manual"
        self.conf[ifname] = ifconf

        self.write()

    def set_static(
        self,
        ifname: str,
        addr: str,
        netmask: str,
        gateway: str | None = None,
        nameservers: list[str] | None = None,
    ) -> None:
        if ifname not in self.conf:
            self.gen_default_if_config(ifname)

        ifconf = _preprocess_interface_config("\n".join(self.conf[ifname]))
        ifconf[1] = f"iface {ifname} inet static"

        ifconf.extend([f"    address {addr}", f"    netmask {netmask}"])

        if gateway:
            ifconf.append(f"    gateway {gateway}")
        if nameservers:
            joined_nameservers = " ".join(nameservers)
            ifconf.append(f"    dns-nameservers {joined_nameservers}")

        self.conf[ifname] = ifconf
        self.write()

    def get_if_conf(self, ifname: str, key: str) -> list[str] | None:
        if ifname in self.conf:
            for line in self.conf:
                line_list = line.strip().split()
                if line_list[0] == key:
                    return line_list[1:]

    def get_nameservers(self, ifname: str) -> list[str] | None:
        return self.get_if_conf(ifname, "dns-nameservers") or []

    def get_address(self, ifname: str) -> str | None:
        addr = self.get_if_conf(ifname, "address")
        if addr:
            return addr[0]

    def get_netmask(self, ifname: str) -> str | None:
        addr = self.get_if_conf(ifname, "netmask")
        if addr:
            return addr[0]


def _parse_resolv(path: str) -> list[str]:
    nameservers = []
    with open(path) as fob:
        for line in fob:
            if line.startswith("nameserver"):
                nameservers.append(line.strip().split()[1])
    return nameservers


def get_nameservers(ifname: str) -> list[str]:
    # /etc/network/interfaces
    interfaces = NetworkInterfaces()
    interfaces.read()

    nameservers = interfaces.get_nameservers(ifname)
    if nameservers:
        return nameservers

    # resolvconf (dhcp)
    path = "/etc/resolvconf/run/interface"
    if os.path.exists(path):
        for f in os.listdir(path):
            if not f.startswith(ifname) or f.endswith(".inet"):
                continue

            nameservers = _parse_resolv(os.path.join(path, f))
            if nameservers:
                return nameservers

    # /etc/resolv.conf (fallback)
    return _parse_resolv("/etc/resolv.conf")


def ifup(ifname: str, force: bool = False) -> str:
    # force is not the same as --force. Here force will configure regardless of
    # errors

    if force:
        ifup_args = ["/usr/sbin/ifup", "--force", "--ignore-errors", ifname]
    else:
        ifup_args = ["/usr/sbin/ifup", "--force", ifname]

    ifup_cmd = subprocess.run(ifup_args, capture_output=True, text=True)

    if not force and ifup_cmd.returncode != 0:
        raise BadIfConfigError(
            f"failed to bring up interface {ifname!r} error:"
            f" {ifup_cmd.stderr!r}"
        )
    return ifup_cmd.stderr


def ifdown(ifname: str, force: bool = False) -> str:
    # force is not the same as --force. Here force will configure regardless of
    # errors

    if force:
        ifdown_args = [
            "/usr/sbin/ifdown", "--force", "--ignore-errors", ifname
        ]
    else:
        ifdown_args = ["/usr/sbin/ifdown", "--force", ifname]

    ifdown_cmd = subprocess.run(ifdown_args, capture_output=True, text=True)

    if ifdown_cmd.returncode != 0:
        raise BadIfConfigError(
                f"failed to bring down interface {ifname!r}"
                f" error: {ifdown_cmd.stderr!r}"
            )
    return ifdown_cmd.stderr


def unconfigure_if(ifname: str) -> str | None:
    try:
        ifdown(ifname)
    except Exception as e:
        return str(e)

    interfaces = NetworkInterfaces()
    interfaces.read()
    backup_interfaces = interfaces.duplicate()
    interfaces.set_manual(ifname)

    try:
        subprocess.check_output(["/usr/sbin/ifconfig", ifname, "0.0.0.0"])
    except subprocess.CalledProcessError as e:
        return str(e)

    try:
        ifup(ifname)
    except Exception as e:
        backup_interfaces.write()
        ifup(ifname, force=True)

        return str(e)


def set_static(
    ifname: str, addr: str, netmask: str, gateway: str, nameservers: list[str]
) -> str | None:
    try:
        addr = str(IPv4.parse(addr))
        netmask = str(IPv4.parse(netmask))
        gateway = str(IPv4.parse(gateway))
        nameservers = [
            str(IPv4.parse(nameserver)) for nameserver in nameservers
        ]

        ifdown(ifname, True)

        interfaces = NetworkInterfaces()
        interfaces.read()
        backup_interfaces = interfaces.duplicate()

        try:
            interfaces.set_static(ifname, addr, netmask, gateway, nameservers)
            sleep(0.5)
        except Exception as e:
            backup_interfaces.write()
            raise e
        finally:
            output = ifup(ifname, True)

        net = InterfaceInfo(ifname)
        if not net.address:
            raise IfError(f"Error obtaining IP address\n\n{output}")

        return None
    except Exception as e:  # TODO - this is essentially a bare except
        return str(e)


def set_dhcp(ifname: str) -> str | None:
    try:
        ifdown(ifname, True)

        interfaces = NetworkInterfaces()
        interfaces.read()
        backup_interfaces = interfaces.duplicate()
        try:
            interfaces.set_dhcp(ifname)
        except Exception as e:
            backup_interfaces.write()
            raise e
        finally:
            output = ifup(ifname, True)

        net = InterfaceInfo(ifname)
        if not net.address:
            raise IfError(f"Error obtaining IP address\n\n{output}")
        return None
    except Exception as e:
        return str(e)


def get_ipconf(
    ifname: str, error: bool = False
) -> tuple[str | None, str | None, str | None, list[str]]:
    net = InterfaceInfo(ifname)
    for _ in range(6):
        net = InterfaceInfo(ifname)
        if net.address is not None and net.netmask is not None:
            gateway = net.get_gateway(error)
            return (net.address, net.netmask, gateway, get_nameservers(ifname))
        sleep(0.1)

    # no interfaces up
    return (None, None, net.get_gateway(error), get_nameservers(ifname))


def get_ifmethod(ifname: str) -> str | None:
    interfaces = NetworkInterfaces()
    interfaces.read()
    conf_line = interfaces.get_if_conf(ifname, "iface")
    if conf_line:
        return conf_line[3]
