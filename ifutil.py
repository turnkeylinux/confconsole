
import re
import time
import fcntl
import struct
import socket

from executil import system, getoutput

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

    def set_ipaddr(self, addr):
        if addr == self.addr or addr == "":
            return

        system("ifconfig %s %s up" % (self.ifname, addr))

    def set_netmask(self, netmask):
        if netmask == self.netmask or netmask == "":
            return

        system("ifconfig %s netmask %s" % (self.ifname, netmask))

    def set_gateway(self, gateway):
        if gateway == self.gateway or gateway == "":
            return

        if self.gateway:
            system("route del default gw %s" % self.gateway)

        for i in range(3):
            try:
                system("route add default gw %s" % gateway)
                break
            except:
                time.sleep(1)

    def set_nameserver(self, nameserver):
        if self.nameserver == nameserver:
            return

        fh = file('/etc/resolv.conf', "w")
        print >> fh, "nameserver %s" % nameserver
        fh.close()

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


def valid_ipv4(addr):
    ip4_re = re.compile(r'^(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}$') 
    if not ip4_re.search(addr):
        return False
    return True

# convenience functions

IFNAME = 'eth0'
def get_ipinfo():
    nic = NIC(IFNAME)
    return nic.addr, nic.netmask, nic.gateway, nic.nameserver

def set_ipinfo(ipaddr, netmask, gateway, nameserver):
    nic = NIC(IFNAME)
    nic.set_ipaddr(ipaddr)
    nic.set_netmask(netmask)
    nic.set_gateway(gateway)
    nic.set_nameserver(nameserver)

def get_hostname():
    return socket.gethostname()


