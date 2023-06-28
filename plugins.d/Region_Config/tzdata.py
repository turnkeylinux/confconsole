'''Reconfigure TZdata '''
import subprocess


def run():
    flag = []
    if not interactive:
        tz = os.getenv('TZ')

        if tz:
            with open('/etc/timezone', 'w') as f:
                f.write(tz)

        flag = ['-f', 'noninteractive']

    subprocess.run(['dpkg-reconfigure', *flag, 'tzdata'],
                   stderr=subprocess.DEVNULL)
