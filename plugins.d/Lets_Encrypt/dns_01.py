#!/usr/bin/python3
import sys
import subprocess
import re

from os import makedirs, chmod, chown
from os.path import isfile, join, exists, dirname
from shutil import which, copy

from typing import Optional

LEXICON_SHARE_DIR = "/usr/share/confconsole/letsencrypt"
LEXICON_CONF_DIR = "/etc/dehydrated"


def load_config(provider: str) -> tuple[str, list[str]]:
    """Loads lexicon config if present, loads example if not,
    returns tuple(conf_file, list(config))
    """
    if provider in ["route53", "cloudflare"]:
        example_conf = join(
            LEXICON_SHARE_DIR, f"lexicon-confconsole-provider_{provider}.yml"
        )
    else:
        example_conf = join(
            LEXICON_SHARE_DIR, "lexicon-confconsole-provider_example.yml"
        )
    conf_file = join(LEXICON_CONF_DIR, f"lexicon_{provider}.yml")
    config = []
    if not isfile(conf_file):
        copy(example_conf, conf_file)
        # ensure root read/write only as file contains sensitive info
        chown(conf_file, 0, 0)  # chown root:root
        chmod(conf_file, 0o600)  # chmod 600 (owner read/write only)
    with open(conf_file) as fob:
        for line in fob:
            config.append(line.rstrip())

    return conf_file, config


def save_config(conf_file: str, config: list[str]) -> None:
    """Saves lexicon configuration"""
    with open(conf_file, "w") as fob:
        for line in config:
            if line:
                fob.write(line.rstrip() + "\n")
    # ensure root read/write only as file contains sensitive info
    chown(conf_file, 0, 0)  # chown root:root
    chmod(conf_file, 0o600)  # chmod 600 (owner read/write only)


def run_command(
    command: list[str], env: Optional[dict[str, str]] = None
) -> tuple[int, str]:
    """Simple subprocess wrapper for running commands"""
    if env is None:
        env = {}
    proc = subprocess.run(command, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        com = " ".join(command)
        return (
            proc.returncode,
            f"Something went wrong when running '{com}':\n\n{proc.stderr}",
        )
    else:
        return 0, "success"


def apt_install(pkgs: list[str]) -> tuple[int, str]:
    """Takes a list of package names, updates apt and installs packages,
    returns tuple(exit_code, message)
    """
    string = ""
    exit_code = 0
    env = {"DEBIAN_FRONTEND": "noninteractive"}
    for command in [
        ["apt-get", "update"],
        ["apt-get", "install", *pkgs, "--yes"],
    ]:
        exit_code, string = run_command(command, env=env)
        if exit_code != 0:
            return exit_code, string
    return exit_code, string


def check_pkg(pkg: str) -> bool:
    """Takes a package name and returns True if installed, otherwise False"""
    p = subprocess.run(
        ["dpkg", "-s", pkg],
        capture_output=True,
        text=True,
    )
    if p.returncode == 0:
        return True  # package installed
    return False  # package not installed


def initial_setup() -> None:
    """Check lexicon and deps are installed and ready to go

    Returns a tuple of exit code (0 = success) and message
    """
    msg_start = "lexicon tool is required for dns-01 challenge, "
    msg_mid = ""
    msg_end = "\n\nDo you wish to continue?"
    msg: str | None = ""
    install_venv = False
    unexpected = False

    lexicon_bin = which("turnkey-lexicon")
    venv = "/usr/local/src/venv/lexicon"
    if not exists(venv):
        # turnkey lexicon venv wrapper not found - offer to install
        install_venv = True
        msg_mid = "however it is not found on your system, so installing."
    elif exists(f"{venv}/bin/lexicon"):
        # lexicon venv bin found - no message required
        msg = None
    else:
        msg_mid = "but your system is in an unexpected state"
        unexpected = True
    if msg is not None:
        msg = msg_start + msg_mid + msg_end
        # console is inherited so doesn't need to be defined
        ret = console.yesno(msg, autosize=True)  # type: ignore[name-defined]
        if ret != "ok":
            return
    if install_venv or unexpected:
        pkgs = []
        pip = which("pip")
        python3_venv = check_pkg("python3-venv")
        if not pip:
            pkgs.append("python3-pip")
        if not python3_venv:
            pkgs.append("python3-venv")
        if pkgs:
            print("Please wait while required packages are installed")
            exit_code, msg = apt_install(pkgs)
            if exit_code != 0:
                pkgs_l = " ".join(pkgs)
                console.msgbox(  # type: ignore[name-defined]
                    "Error", f"Apt installing {pkgs_l} failed:\n\n{msg}"
                )
        makedirs(dirname(venv), exist_ok=True)
        venv_pip = join(venv, "bin/pip")
        for comment_command in [
            ("venv is set up", ["/usr/bin/python3", "-m", "venv", venv]),
            (
                "lexicon is installed (into venv)",
                [venv_pip, "install", "dns-lexicon[full]"],
            ),
        ]:
            comment, command = comment_command
            assert isinstance(command, list)
            if comment:
                print(f"Please wait while {comment}")
            exit_code, msg = run_command(command)
            if exit_code != 0:
                com = " ".join(command)
                console.msgbox(  # type: ignore[name-defined]
                    "Error", f"Command '{com}' failed:\n\n{msg}"
                )
                return None

        lexicon_bin = which("turnkey-lexicon")
        if not lexicon_bin:
            console.msgbox(  # type: ignore[name-defined]
                "Error",
                "Could not find 'turnkey-lexicon'? Should be installed with"
                " Confconsole.",
            )
        return None


def get_providers() -> tuple[list[tuple[str, str]] | None, str | None]:
    """Get list of supported DNS providers from lexicon"""
    lexicon_bin = which("turnkey-lexicon")
    if not lexicon_bin:
        return (
            None,
            "turnkey-lexicon is not found on your system, is it installed?",
        )
    print("Please wait while list of supported DNS providers is downloaded")
    proc = subprocess.run(
        [lexicon_bin, "--lexicon-help"],
        encoding=sys.stdin.encoding,
        capture_output=True,
    )
    if proc.returncode != 0:
        return None, proc.stderr.strip()

    match = re.search(r"(?<={).*(?=})", proc.stdout.strip())
    if not match:
        return None, "Could not obtain DNS providers list from lexicon!"

    providers = []
    for provider in match.group().split(","):
        if len(provider) > 0:
            providers.append((provider, f"{provider} provider"))

    if providers:
        return providers, None
    return None, "DNS providers list is empty!"
