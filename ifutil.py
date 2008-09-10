
import re
import fcntl
import struct
import socket

from executil import getoutput

SIOCGIFADDR = 0x8915
SIOCGIFNETMASK = 0x891b
SIOCGIFBRDADDR = 0x8919

def _readfile(path):
    fh = file(path)
    lines = fh.readlines()
    fh.close()
    return lines

class NIC:
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

    def __getattr__(self, attrname):
        if attrname in self.ATTRIBS.ADDRS:
            return self._get_addr(self.ATTRIBS.ADDRS[attrname])

        if attrname == "gateway":
            m = re.search('^0.0.0.0\s+(.*?)\s', getoutput("route -n"), re.M)
            if m:
                return m.group(1)
            return None

        if attrname == "nameserver":
            for line in _readfile('/etc/resolv.conf'):
                if line.startswith('nameserver'):
                    try:
                        junk, nameserver = line.strip().split()
                        return nameserver
                    except:
                        pass
            return None


# convenience functions

def get_ipinfo(ifname='eth1'):
    nic = NIC(ifname)
    return nic.addr, nic.netmask, nic.gateway, nic.nameserver

def get_hostname():
    return socket.gethostname()


