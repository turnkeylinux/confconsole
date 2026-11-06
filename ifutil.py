import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from ipaddress import ip_address
from os.path import join, exists
from time import sleep

from netinfo import InterfaceInfo
from netinfo import get_hostname

log = logging.getLogger(__name__)


class IfError(Exception):
    pass


class InvalidIPError(IfError):
    pass


class InvalidIPv4Error(InvalidIPError):
    pass


class InvalidIPv6Error(InvalidIPError):
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


def _list_to_data(lines: list[str]) -> list[str | dict[str, str | list[str]]]:
    """Split an ifutil interface info list into iface-stanza 'data' format.

    E.g.:
    iface_lines = [
        'auto eth0',
        'iface eth0 inet dhcp', '    hostname core',
        'iface eth0 inet6 dhcp', '    hostname core',
    ]
    Returns:
    [
        'auto eth0',
        {
            'iface': 'eth0',
            'family': 'inet',
            'method': 'dhcp',
            'options': [['hostname', 'core']],
        },{
            'iface': 'eth0'
            'family': 'inet6',
            'method': 'dhcp',
            'options': [['hostname', 'core'],
        },
    ]
    """
    # this (somewhat) duplicates the function of other code here, however the
    # existing code isn't ipv6 aware - this explictly supports splitting ipv4
    # and ipv6 config and IMO provides a nicer interface to work with
    blocks: list[str | dict[str, str | list[str]]] = []
    current = None

    for line in lines:
        is_indented = line.startswith((" ", "\t"))
        if not is_indented:
            # starting a new top-level record -> close off any open stanza
            if current is not None:
                blocks.append(current)
                current = None

            if line.strip().startswith("iface"):
                iface_header = line.strip()
                if len(iface_header.split()) != 4:
                    raise BadIfConfigError(
                        f"Invalid iface header: '{iface_header}'",
                    )
                iface, family, method = iface_header.split()[1:4]
                current = {
                    "iface": iface,
                    "family": family,
                    "method": method,
                    "options": [],
                }
            else:
                blocks.append(line)  # "auto eth0", comments, blank lines...
        else:
            if current is not None:
                # replace existing indent with 4 spaces
                current["options"].append(line.strip().split())
            else:
                # indented line with no open stanza (shouldn't normally
                # happen) - keep it so nothing gets silently dropped
                blocks.append(line)
    if current is not None:
        blocks.append(current)
    return blocks


def _data_to_list(
    iface_data: list[str | dict[str, str | list[str]]],
) -> list[str]:
    """Convert iface 'data' info back to standard interface lines list."""
    iface_list = []
    for item in iface_data:
        if isinstance(item, str):
            iface_list.append(item)
        else:
            iface_list.append(
                f"iface {item['iface']} {item['family']} {item['method']}"
            )
            for option in item["options"]:
                iface_list.append(f"    {' '.join(option)}")
    return iface_list


def _get_raw_opts(
        iface_lines: list[str], inet_family: str = "inet",
) -> list[list[str]]:
    """Parse iface info list and return a list of options split into lists."""
    for section in _list_to_data(iface_lines):
        if "family" in section and section["family"] == inet_family:
            return section["options"]
    return []


def _merge_iface_options(
        current_opts: list[list[str]],
        new_opts: dict[str, str | list[str] | None],
) -> list[list[str]]:
    """Merge existing iface options with new ones.

    Args:
        current_opts (list[list[str]]):
            List of interface stanza option lines - each item in a line split
            into a list.
        new_opts (dict[str, str | list[str] | None]):
            Dictionary of key/value option pairs to add to/overide
            'current_opts'.

    Note:
        'new_opts':
            - Keys which have string or list values are added to the start of
              the updated options list as a list (split on whitespace char).
              E.g. ['key', 'value1', 'value2'].
            - Keys with None value are ignored.
            - If a key already exists in 'current_opts' the value from new_opts
              will override it.
            - If a hostname entry does not exist in either dataset, one will be
              generated and included as the first item in the return list.
            - All remaining items from 'current_opts' will be retained
              verbatum.

    Returns:
        list[list[str]]:
            List of merged interface stanza option lines in same format as
            'current_opts'.
    """
    # map var -> key name, keep only ones that have a value
    new_opts = {k: v for k, v in new_opts.items() if v is not None}

    # remove hostname if it exists in new_opts
    try:
        new_hostname = new_opts.pop("hostname")
    except KeyError:
        new_hostname = None

    def format_value(v: str | list[str]) -> str:
        # convert value lists to space separated string.
        # E.g. join list of nameservers
        if isinstance(v, list):
            return " ".join(v)
        return str(v)

    # new/updated values go first
    final_list = []
    for k, v in new_opts.items():
        if isinstance(v, str):
            final_list.append([k, *v.split()])
        else:
            final_list.append([k, *v])

    # then existing lines, skipping any whose key we've already replaced
    for opt in current_opts:
        if opt[0] == "hostname" and not new_hostname:
            new_hostname = opt[1]
            continue
        elif opt[0] in new_opts:
            continue  # new value override already set
        final_list.append(opt)  # untouched

    # add hostname back in as first item
    final_list.insert(0, ["hostname", new_hostname or get_hostname()])

    return final_list


def _strip_static_opts(options: list[list[str]]) -> list[list[str]]:
    """Strips unwanted/irrelevant options for dhcp iface.

    Accepts a list of iface option lists - i.e. as stored in iface-stanza
    'data'. Any options that are common in static config, but don't make sense
    in a dhcp iface will be removed.

    Returns data in the same format - i.e.:
        [
            ['option_key1', 'option_value1'],
            ['option_key2', 'option_value2.0', 'option_value2.1'],
            [...],
        ]

    Also:
        - Ensures a hostname line exists. If it's missing, one will be added.
        - Ensures hostname is the first option.
    """
    updated_options = []
    hostname = ["hostname", get_hostname()]
    for option in options:
        if option[0] in (
            "address", "netmask", "gateway", "dns-nameservers",
        ):
            continue
        elif option[0] == "hostname":
            hostname = option
            continue
        updated_options.append(option)

    updated_options.insert(0, hostname)
    return updated_options


def _valid_ip(ip: str) -> str:
    """Validate an IP address.

    Returns:
        str:
            Validated IPv4 or IPv6 address.

    Note:
        - A valid IP/CIDR is considered an invalid IP.

    Raises:
        InvalidIPError:
            - If IP is not a valid IPv4 or IPv6 (including valid IP/CIDR).
    """
    if "/" in ip:
        # ipaddress.ip_address(ip/cidr) is considered a valid ip
        raise InvalidIPError(f"Must be plain IP, not IP/CIDR: '{ip}'")
    try:
        _ip = ip_address(ip)
    except ValueError as e:
        raise InvalidIPError(str(e)) from e
    return ip


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

    def _get_opts_subset(
        self, ifname: str, opts: list[str], inet_family: str = "inet",
    ) -> list[str]:
        if ifname not in self.conf:
            raise InterfaceNotFoundError(f"no existing config for {ifname}")
        ifconf_block = _list_to_data(self.conf[ifname])
        option_subset = []
        for stanza in ifconf_block:
            if "family" in stanza and stanza["family"] == inet_family:
                for option in stanza["options"]:
                    if option[0] in opts:
                        option_subset.append(" ".join(option))
        return option_subset

    def get_iface_opts(self, ifname: str, inet_fam: str = "inet") -> list[str]:
        return self._get_opts_subset(ifname, self._iface_opts, inet_fam)

    def get_bridge_opts(self, ifname: str, inet_fam: str = "inet") -> list[str]:
        return self._get_opts_subset(ifname, self._bridge_opts, inet_fam)

    def get_method(self, ifname: str, inet_fam: str = "inet") -> str:
        if ifname not in self.conf:
            return ""
        iface_data = _list_to_data(self.conf[ifname])
        for stanza in iface_data:
            if "family" in stanza and stanza["family"] == inet_fam:
                return stanza["method"]
        return ""

    def duplicate(self) -> "NetworkInterfaces":
        interfaces = NetworkInterfaces()
        interfaces.unconfigured = self.unconfigured
        interfaces.conf = {
            key: [i for i in value] for key, value in self.conf.items()
        }
        return interfaces

    def read(self, conf_file: str | None = None) -> None:
        if conf_file is None:
            conf_file = self.CONF_FILE
        # clear config
        self.conf = {}
        self.unconfigured = False

        ifname: str | None = None

        with open(conf_file) as fob:
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

    def write(self, conf_file: str | None = None) -> None:
        if conf_file is None:
            conf_file = self.CONF_FILE
        if not self.unconfigured:
            raise ManuallyConfiguredError(
                f"refusing to write to {conf_file}\n"
                f"header not found: {self.HEADER_UNCONFIGURED}"
            )

        with open(conf_file, "w") as fob:
            fob.write(self.HEADER_UNCONFIGURED + "\n\n")
            for iface in self.conf.keys():
                fob.write("\n")
                fob.write("\n".join(self.conf[iface]))
                fob.write("\n")

    def gen_default_if_config(
        self, ifname: str, inet_family: str = "both",
    ) -> None:
        """Generate an eth interface config with DHCP IPv4 &/or IPv6.

        Args:
            ifname (str):
                Interface name - e.g. 'eth0'
            inet_family (str):
                One of:
                    'both'  - IPv4 and IPv6 stanzas.
                    'inet'  - IPv4 stanza only (IPv6 disabled)
                    'inet6' - IPv6 stanza only (IPv4 disabled)

        Raises:
            InterfaceNotFoundError:
                If ``iface`` is not an ethernet interface (starts with 'e').
        """
        if ifname.startswith("e"):
            iface_txt_block = [f"auto {ifname}"]
            if inet_family in ("both", "inet"):
                iface_txt_block.extend([
                    f"iface {ifname} inet dhcp",
                    f"    hostname {get_hostname()}"
                ])
            if inet_family in ("both", "inet6"):
                iface_txt_block.extend([
                    f"iface {ifname} inet6 dhcp",
                    f"    hostname {get_hostname()}"
                ])

            self.conf[ifname] = _preprocess_interface_config(
                "\n".join(iface_txt_block)
            )
        else:
            raise InterfaceNotFoundError(f"no existing config for {ifname}")

    def set_dhcp(self, ifname: str) -> None:
        """Set interface IPv4 method to DHCP.

        If interface does not exist, a new one will be created with IPv4 & IPv6
        both set to DHCP. Otherwise IPv6 conf will not be changed.
        """
        if ifname not in self.conf:
            self.gen_default_if_config(ifname, "both")
            return
        ifconf_data = _list_to_data(self.conf[ifname])
        for index, stanza in enumerate(ifconf_data):
            if "family" in stanza and stanza["family"] == "inet":
                ifconf_data[index]["method"] = "dhcp"
                ifconf_data[index]["options"] = _strip_static_opts(
                    stanza["options"],
                )
                break
        self.conf[ifname] = _data_to_list(ifconf_data)


    def set_manual(self, ifname: str) -> None:
        """Set interface IPv4 method to manual.

        If interface does not exist, a new one will be created with IPv4 & IPv6
        both set to DHCP. Otherwise IPv6 conf will not be changed.
        """
        if ifname not in self.conf:
            self.gen_default_if_config(ifname)
        ifconf_data = _list_to_data(self.conf[ifname])
        for index, stanza in enumerate(ifconf_data):
            if "family" in stanza and stanza["family"] == "inet":
                ifconf_data[index]["method"] = "manual"
                ifconf_data[index]["options"] = _strip_static_opts(
                    stanza["options"],
                )
                break
        self.conf[ifname] = _data_to_list(ifconf_data)

    def set_static(
        self,
        ifname: str,
        addr: str,
        netmask: str,
        gateway: str | None = None,
        nameservers: list[str] | None = None,
    ) -> None:
        """Set interface IPv4 method to static.

        Stanza option indents will be (re)set to 4 spaces.

        If interface does not exist, a new one will be created with IPv4 & IPv6
        set to static & DHCP respectively. Otherwise IPv6 conf will not be
        changed.
        """
        if ifname not in self.conf:
            self.gen_default_if_config(ifname, "both")
        ifconf_block = _list_to_data(self.conf[ifname])
        # address & netmask are always set; gateway & dns-nameservers are
        # optional. Only include the optional keys when supplied - combined
        # with stripping the existing static options below, this ensures an
        # omitted/cleared field is actually removed rather than retained.
        new_conf_dict: dict[str, str | list[str] | None] = {
            "address": addr,
            "netmask": netmask,
        }
        if gateway:
            new_conf_dict["gateway"] = gateway
        if nameservers:
            # note that both ipv4 & ipv6 IPs are valid regardless of iface
            # inet family
            new_conf_dict["dns-nameservers"] = [
                ns for ns in nameservers if _valid_ip(ns)
            ]

        for index, stanza in enumerate(ifconf_block):
            if "family" in stanza and stanza["family"] == "inet":
                ifconf_block[index]["method"] = "static"
                # drop any existing address/netmask/gateway/dns-nameservers
                # first so that omitted optional fields don't linger
                stripped = _strip_static_opts(stanza["options"])
                ifconf_block[index]["options"] = _merge_iface_options(
                    stripped, new_conf_dict,
                )
        self.conf[ifname] = _data_to_list(ifconf_block)

    def get_if_conf(
        self, ifname: str, key: str, inet_family = "inet",
    ) -> list[str] | None:
        if ifname in self.conf:
            for stanza in _list_to_data(self.conf[ifname]):
                if "family" in stanza and stanza["family"] == inet_family:
                    for option in stanza["options"]:
                        if option[0] == key:
                            return option[1:]
        return None

    def get_nameservers(self, ifname: str) -> list[str] | None:
        return self.get_if_conf(ifname, "dns-nameservers") or []

    def get_address(self, ifname: str) -> str | None:
        addr = self.get_if_conf(ifname, "address")
        if addr:
            return addr[0]
        return None

    def get_netmask(self, ifname: str) -> str | None:
        addr = self.get_if_conf(ifname, "netmask")
        if addr:
            return addr[0]
        return None

    def __repr__(self) -> str:
        return json.dumps(self.conf, indent=4)


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
    if exists(path):
        for f in os.listdir(path):
            if not f.startswith(ifname) or f.endswith(".inet"):
                continue

            nameservers = _parse_resolv(join(path, f))
            if nameservers:
                return nameservers

    # /etc/resolv.conf (fallback)
    return _parse_resolv("/etc/resolv.conf")


def ifup(ifname: str, force: bool = False, *, check: bool = False) -> str:
    # Recovery callers may ignore forced errors; checked applies must report them.
    ifup_args = ["/usr/sbin/ifup"]
    if force:
        ifup_args.append("--force")
    ifup_args.append(ifname)
    log.debug("running: %s", " ".join(ifup_args))
    ifup_cmd = subprocess.run(ifup_args, capture_output=True, text=True)
    log.debug(
        "ifup %s -> rc=%s stderr=%r",
        ifname,
        ifup_cmd.returncode,
        ifup_cmd.stderr,
    )
    if (check or not force) and ifup_cmd.returncode != 0:
        log.error("failed to bring up %r: %s", ifname, ifup_cmd.stderr)
        raise BadIfConfigError(
            f"failed to bring up interface {ifname!r} error:"
            f" {ifup_cmd.stderr!r}"
        )
    return ifup_cmd.stderr


def ifdown(ifname: str, force: bool = False) -> str:
    # force will add the '--force' switch and ignore errors
    ifdown_args = ["/usr/sbin/ifdown"]
    if force:
        ifdown_args.append("--force")
    ifdown_args.append(ifname)
    log.debug("running: %s", " ".join(ifdown_args))
    ifdown_cmd = subprocess.run(ifdown_args, capture_output=True, text=True)
    log.debug(
        "ifdown %s -> rc=%s stderr=%r",
        ifname,
        ifdown_cmd.returncode,
        ifdown_cmd.stderr,
    )
    if not force and ifdown_cmd.returncode != 0:
        log.error("failed to bring down %r: %s", ifname, ifdown_cmd.stderr)
        raise BadIfConfigError(
            f"failed to bring down interface {ifname!r} error:"
            f" {ifdown_cmd.stderr!r}"
        )
    return ifdown_cmd.stderr


def unconfigure_if(ifname: str, force: bool = False) -> str | None:
    err = ifdown(ifname, force=force)
    if err and not force:
        log.error("unconfigure_if failed for %s", ifname)
        return err
    
    interfaces = NetworkInterfaces()
    interfaces.read()
    backup_interfaces = interfaces.duplicate()
    interfaces.set_manual(ifname)
    interfaces.write()

    try:
        subprocess.check_output(
            ["/usr/sbin/ip", "addr", "flush", "dev", ifname],
        )
        fail = False
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        if not force:
            return str(e)
        # forcing: fall through and try flushing addr + route explicitly
        fail = True

    if fail:
        for arg in ("addr", "route"):
            cmd = ["/usr/sbin/ip", arg, "flush", "dev", ifname]
            ip_proc = subprocess.run(cmd, capture_output=True, text=True)
            if ip_proc.returncode != 0:
                # bail now - even with force - something is very wrong!
                raise BadIfConfigError(ip_proc.stderr)
    try:
        ifup(ifname)
    except Exception as e:
        backup_interfaces.write()
        ifup(ifname, force=True)
        return str(e)
    return None


def set_static(
    ifname: str, addr: str, netmask: str, gateway: str, nameservers: list[str]
) -> str | None:
    """Set a static IPv4 for 'ifname'."""
    try:
        addr = str(IPv4.parse(addr))
        netmask = str(IPv4.parse(netmask))
        # gateway is optional (e.g. a secondary NIC or an isolated network);
        # only parse/set it when actually provided
        gw = str(IPv4.parse(gateway)) if gateway else None
        # note that IPv6 addresses are valid as IPv4 nameservers
        nameservers = [_valid_ip(ns) for ns in nameservers]

        ifdown(ifname, force=True)

        interfaces = NetworkInterfaces()
        interfaces.read()
        backup_interfaces = interfaces.duplicate()

        try:
            interfaces.set_static(ifname, addr, netmask, gw, nameservers)
            interfaces.write()
            sleep(0.5)
        except Exception as e:
            backup_interfaces.write()
            raise e
        finally:
            output = ifup(ifname, True, check=True)

        net = InterfaceInfo(ifname)
        if not net.address:
            raise IfError(f"Error obtaining IP address\n\n{output}")

        return None
    except Exception as e:  # TODO - this is essentially a bare except
        log.exception("set_static failed for %s", ifname)
        return str(e)


def set_dhcp(ifname: str) -> str | None:
    try:
        ifdown(ifname, True)

        interfaces = NetworkInterfaces()
        interfaces.read()
        backup_interfaces = interfaces.duplicate()
        try:
            interfaces.set_dhcp(ifname)
            interfaces.write()
        except Exception as e:
            backup_interfaces.write()
            raise e
        finally:
            output = ifup(ifname, True)
        for _retry in range(10):
            net = InterfaceInfo(ifname)
            if net.address:
                break
            sleep(1)
        if not net.address:
            raise IfError(f"Error obtaining IP address\n\n{output}")
        return None
    except Exception as e:
        log.exception("set_dhcp failed for %s", ifname)
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


def get_ipv6conf(ifname: str) -> tuple[str | None, str | None]:
    """Get IPv6 global address and prefix for an interface."""
    try:
        out = subprocess.check_output(
            ["ip", "-6", "addr", "show", ifname, "scope", "global"],
            text=True, stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet6"):
                parts = line.split()
                addr_prefix = parts[1]
                addr, prefix = addr_prefix.split("/")
                return (addr, prefix)
    except Exception:
        pass
    return (None, None)


def get_ifmethod(ifname: str, inet_family: str = "inet") -> str | None:
    interfaces = NetworkInterfaces()
    interfaces.read()
    method = interfaces.get_method(ifname, inet_family)
    if method:
        return method
    return None
