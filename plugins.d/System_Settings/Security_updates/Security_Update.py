"""Install security updates now"""

from subprocess import check_call, CalledProcessError


def run():
    try:
        check_call(["turnkey-install-security-updates"])
    except CalledProcessError:
        console.msgbox("An error occurred while running security updates!")
