"""Reconfigure Keyboard"""

import subprocess
from subprocess import check_output, check_call


def is_installed(pkg: str) -> bool:
    for line in check_output(
        ["apt-cache", "policy", pkg], text=True
    ).splitlines():
        if line.startswith("  Installed"):
            _, val = line.split(":")
            if val.strip() in ("(none)", ""):
                return False
    return True


def run():
    flag = []
    # interactive is inherited so doesn't need to be defined
    if interactive:
        to_install = []
        for package in ["console-setup", "keyboard-configuration"]:
            if not is_installed(package):
                to_install.append(package)
        if to_install:
            ret = console.yesno(
                "The following package(s) is/are required for this"
                " operation:\n\n"
                f"    {' '.join(to_install)}\n\n"
                "Do you wish to install now?",
                autosize=True,
            )

            if ret == "ok":
                check_call(["apt-get", "-y", "install", *to_install])
            else:
                return

        ret = console.yesno(
            "Note: If new keyboard settings are not applied, you may need"
            " to reboot your operating system. Continue with"
            " configuration?",
            autosize=True,
        )

        if ret != 0:
            return
    else:
        flag = ["-f", "noninteractive"]

    subprocess.run(["dpkg-reconfigure", "keyboard-configuration", *flag])
    subprocess.run(
        ["udevadm", "trigger", "--subsystem-match=input", "--action=change"]
    )
    subprocess.run(["service", "keyboard-setup", "restart"])
