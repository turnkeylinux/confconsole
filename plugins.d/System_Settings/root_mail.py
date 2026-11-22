"""Choose whether server mail goes to the security contact."""
import subprocess

menu_label = "System mail forwarding"


def run():
    try:
        subprocess.run(['/usr/lib/inithooks/bin/rootmail.py'], check=True)
    except (OSError, subprocess.CalledProcessError):
        console.msgbox('System mail forwarding', 'Could not open this setting. Update inithooks and try again.', autosize=True)
