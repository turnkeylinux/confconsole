# Copyright (c) 2008-2019 Alon Swartz <alon@turnkeylinux.org> - all rights reserved
# Copyright (c) 2020 TurnKey GNU/Linux <admin@turnkeylinux.org> - all rights reserved

import re
import os
from typing import Optional


class Error(Exception):
    pass


def path(filename: str) -> str:
    for dir in ("conf", "/etc/confconsole"):
        path = os.path.join(dir, filename)
        if os.path.exists(path):
            return path

    raise Error(f'could not find configuration file: {filename}')


class Conf:
    default_nic: Optional[str]
    publicip_cmd: Optional[str]
    networking: bool
    copy_paste: bool
    conf_file: str

    def _load_conf(self) -> None:
        if not self.conf_file or not os.path.exists(self.conf_file):
            return

        with open(self.conf_file, 'r') as fob:
            for line in fob:
                line = line.strip()

                if not line or line.startswith("#"):
                    continue

                op, val = re.split(r'\s+', line, 1)
                if op == 'default_nic':
                    self.default_nic = val
                elif op == 'publicip_cmd':
                    self.publicip_cmd = val
                elif op == 'networking' and val in ('true', 'false'):
                    self.networking = True if val == 'true' else False
                elif op == 'autostart':
                    pass
                elif op == 'copy_paste' and val.lower() in ('true', 'false'):
                    self.copy_paste = True if val.lower() == 'true' else False
                else:
                    raise Error("illegal configuration line: " + line)

    def __init__(self) -> None:
        self.default_nic = None
        self.publicip_cmd = None
        self.networking = True
        self.copy_paste = True
        self.conf_file = path("confconsole.conf")
        self._load_conf()

    def set_default_nic(self, ifname: str) -> None:
        self.default_nic = ifname

        with open(self.conf_file, 'w') as fob:
            fob.write("default_nic %s\n" % ifname)
