'''Update machine hostname'''

import os

TITLE = 'Update Hostname'

def run():
    ret, new_hostname = console.inputbox(TITLE, 'Please enter the new hostname for this machine:')
    if ret == 0:
        os.system("hostname %s && echo '%s' > /etc/hostname" % (new_hostname, new_hostname))
        console.msgbox(TITLE, 'Hostname updated successfully. Some applications might require a relaunch before the setting applies to them.')
