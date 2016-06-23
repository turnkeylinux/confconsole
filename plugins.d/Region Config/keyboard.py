'''Reconfigure Keyboard '''
import os

def run():
    console.yesno('Note: If new keyboard settings are not applied, you may need to reboot your operating system. Continue with configuration?')
    os.system('dpkg-reconfigure keyboard-configuration')
    os.system('service keyboard-setup restart')
