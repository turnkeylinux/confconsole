
import fcntl
import struct
import socket

SIOCGIFADDR = 0x8915
SIOCGIFNETMASK = 0x891b
SIOCGIFBRDADDR = 0x8919

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


# convenience functions

def get_ipinfo(ifname):
    nic = NIC(ifname)
    return nic.addr, nic.netmask, nic.brdaddr

def get_hostname():
    return socket.gethostname()


