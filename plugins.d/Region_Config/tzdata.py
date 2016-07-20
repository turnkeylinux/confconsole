'''Reconfigure TZdata '''
import os

def run():
    os.system('dpkg-reconfigure tzdata 2> /dev/null')
