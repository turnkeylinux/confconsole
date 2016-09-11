'''Reconfigure Keyboard '''
import os

def run():
    flag = ''

    if interactive:
        ret = console.yesno('Note: If new keyboard settings are not applied, you may need to reboot your operating system. Continue with configuration?')

        if ret != 0:
            return
    else:
        flag = '-f noninteractive'

    os.system('dpkg-reconfigure %s keyboard-configuration' % flag)
    os.system('service keyboard-setup restart')
