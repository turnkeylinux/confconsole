"""Reconfigure TZdata"""

import subprocess
import os


def run():
    flag = []
    # interactive is inherited so doesn't need to be defined
    if not interactive:
        tz = os.getenv("TZ")

        if tz:
            with open("/etc/timezone", "w") as f:
                f.write(tz)

        flag = ["-f", "noninteractive"]

    subprocess.run(
        ["dpkg-reconfigure", *flag, "tzdata"], stderr=subprocess.DEVNULL
    )
