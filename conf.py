# Copyright (c) 2008 Alon Swartz <alon@turnkeylinux.org> - all rights reserved

import re
import os

class Error(Exception):
    pass

def path(filename):
    for dir in ("conf", "/etc/confconsole"):
        path = os.path.join(dir, filename)
        if os.path.exists(path):
            return path

    raise Error('could not find configuration file: %s' % path)

class Conf:
    def _load_conf(self):
        if not os.path.exists(self.conf_file):
            return

        for line in file(self.conf_file).readlines():
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            op, val = re.split(r'\s+', line, 1)
            if op == 'default_nic':
                self.default_nic = val
            else:
                raise Error("illegal configuration line: " + line)

    def __init__(self):
        self.default_nic = None
        self.conf_file = path("confconsole.conf")
        self._load_conf()

    def set_default_nic(self, ifname):
        self.default_nic = ifname

        fh = file(self.conf_file, "w")
        print >> fh, "default_nic %s" % ifname
        fh.close()

