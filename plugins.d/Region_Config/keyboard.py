'''Reconfigure Keyboard '''
import os
from subprocess import check_call, check_output, CalledProcessError


def is_installed(pkg):
    for line in check_output(['apt-cache', 'policy', pkg], text=True).splitlines():
        if line.startswith('  Installed'):
            key, val = line.split(':')
            if val.strip() in ('(none)', ''):
                return False
    return True


def run():
    flag = ''

    if interactive:
        if not is_installed('keyboard-configuration'):
            ret = console.yesno('The keyboard-configuration package is'
                                ' required for this operation, do you wish'
                                ' to install it now?', autosize=True)

            if ret == 'ok':
                check_call(['apt-get', '-y', 'install',
                            'keyboard-configuration'])
            else:
                return

        ret = console.yesno('Note: If new keyboard settings are not applied,'
                            ' you may need to reboot your operating system.'
                            ' Continue with configuration?', autosize=True)

        if ret != 0:
            return
    else:
        flag = '-f noninteractive'

    os.system('dpkg-reconfigure %s keyboard-configuration' % flag)
    os.system('service keyboard-setup restart')
