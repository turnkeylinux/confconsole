import re
import socket
import executil
import fcntl

SIOCGIFADDR = 0x8915
SIOCGIFNETMASK = 0x891b

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

