'''Reconfigure TZdata '''
import os

def run():
    flag = ''
    if not interactive:
        tz = os.getenv('TZ')

        if tz:
            with open('/etc/timezone', 'w') as f:
                f.write(tz)

        flag = '-f noninteractive'

    os.system('dpkg-reconfigure %s tzdata 2> /dev/null' % flag)
