'''Update machine hostname'''

import re
import subprocess
from subprocess import Popen, PIPE

TITLE = 'Update Hostname'


def _validate_hostname(hostname):
    pattern = r"^[-\w]*$"
    hostname_parts = hostname.split('.')
    match_parts = []
    fail_parts = []
    for part in hostname_parts:
        match = re.match(pattern, part)
        if match:
            match_parts.append(part)
        else:
            fail_parts.append(part)
    if len(hostname_parts) == len(match_parts):
        return hostname
    else:
        return None


def _get_current_hostname():
    with open('/etc/hostname') as fob:
        return fob.readline().strip()

def run():
    while True:
        ret, new_hostname = console.inputbox(
                TITLE, 'Please enter the new hostname for this machine:',
                _get_current_hostname())
        if ret == 'ok':
            valid_hostname = _validate_hostname(new_hostname)
            if not valid_hostname:
                console.msgbox(TITLE, '{} ({})'.format(
                    "Invalid hostname", new_hostname))
                continue
            else:
                proc = Popen(["hostname", new_hostname], stderr=PIPE)
                _, out = proc.communicate()
                returncode = proc.returncode

                if returncode:
                    console.msgbox(TITLE, '{} ({})'.format(out, new_hostname))
                    continue

            new_localhost = new_hostname.split('.')[0]

            with open('/etc/hostname', 'w') as fob:
                fob.write(new_localhost + '\n')

            if new_localhost != new_hostname:
                add_hosts = "{} {}".format(new_localhost, new_hostname)
            else:
                add_hosts = new_hostname
            with open('/etc/hosts', 'r') as fob:
                lines = fob.readlines()
            with open('/etc/hosts', 'w') as fob:
                for line in lines:
                    fob.write(
                        re.sub(r'^127\.0\.1\.1 .*',
                               '127.0.1.1 ' + add_hosts, line))

            with open('/etc/postfix/main.cf', 'r') as fob:
                lines = fob.readlines()
            with open('/etc/postfix/main.cf', 'w') as fob:
                for line in lines:
                    fob.write(
                        re.sub(r'myhostname =.*',
                               f'myhostname = {new_hostname}',
                               line))
            with open('/etc/network/interfaces', 'r') as fob:
                lines = fob.readlines()
            with open('/etc/network/interfaces', 'w') as fob:
                for line in lines:
                    fob.write(re.sub(r'hostname .*',
                                     f'hostname {new_hostname}',
                                     line))
            should_restart = console.yesno(
                    "Networking must be restarted to apply these changes. "
                    "However restarting networking may close your ssh "
                    "connection as hostname changes may effect the address "
                    "allocated to you by DHCP. Not restarting may have other "
                    "adverse effects in other software.\n\nDo you want to "
                    "restart networking?", True) == 'ok'

            if should_restart:
                proc = subprocess.run(['systemctl', 'restart', 'networking'])
                proc = subprocess.run(['postfix', 'reload'], stderr=PIPE)
                if proc.returncode != 0:
                    console.msgbox(TITLE,
                                   '{} ({})'.format(out.decode('utf8'), "reloading postfix"))
            console.msgbox(TITLE,
                           'Hostname updated successfully. Some applications'
                           ' may require restart before the settings are'
                           ' applied.')

            break
        else:
            break
