'''Update machine hostname'''

import os
import re
from subprocess import Popen, CalledProcessError, PIPE

TITLE = 'Update Hostname'

def run():
    while True:
        ret, new_hostname = console.inputbox(TITLE, 'Please enter the new hostname for this machine:')
        if ret == 0:
            proc = Popen(["hostname", new_hostname], stderr=PIPE)
            _, out = proc.communicate()
            returncode = proc.returncode

            if returncode:
                console.msgbox(TITLE, '{} ({})'.format(out, new_hostname))
                continue

            with open('/etc/hostname', 'w') as fob:
                fob.write(new_hostname + '\n')

            with open('/etc/hosts', 'r') as fob:
                lines = fob.readlines()
            with open('/etc/hosts', 'w') as fob:
                for line in lines:
                    fob.write(re.sub(r'^127\.0\.1\.1 .*', '127.0.1.1 ' + new_hostname, line))

            with open('/etc/postfix/main.cf', 'r') as fob:
                lines = fob.readlines()
            with open('/etc/postfix/main.cf', 'w') as fob:
                for line in lines:
                    fob.write(re.sub(r'myhostname =.*', 'myhostname = {}'.format(new_hostname), line))

            console.msgbox(TITLE, 'Hostname updated successfully. Some applications might require a relaunch before the setting applies to them.')

            break
        else:
            break
