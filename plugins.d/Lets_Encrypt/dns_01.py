#!/usr/bin/python3
import sys
import subprocess
import re

from os import makedirs, chmod, chown, replace
from os.path import isfile, join, exists, dirname
from shutil import which
from tempfile import NamedTemporaryFile

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
    source = conf_file if isfile(conf_file) else example_conf
    with open(source) as fob:
        for line in fob:
            config.append(line.rstrip("\n"))

    return conf_file, config


def save_config(conf_file: str, config: list[str]) -> None:
    """Saves lexicon configuration"""
    from os import unlink

    with NamedTemporaryFile(mode="w", dir=dirname(conf_file),
                            prefix=".lexicon-", delete=False) as fob:
        temporary = fob.name
        try:
            chown(temporary, 0, 0)
            chmod(temporary, 0o600)
            fob.write("\n".join(config) + "\n")
            fob.close()
            replace(temporary, conf_file)
        finally:
            if exists(temporary):
                unlink(temporary)


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


def install_lexicon() -> bool:
    """Install the existing Confconsole-managed DNS validation tool."""
    venv = "/usr/local/src/venv/lexicon"
    if isfile(f"{venv}/bin/lexicon") and isfile(f"{venv}/bin/activate"):
        return True
    pkgs = []
    if not which("pip"):
        pkgs.append("python3-pip")
    if not check_pkg("python3-venv"):
        pkgs.append("python3-venv")
    if pkgs and apt_install(pkgs)[0]:
        return False
    makedirs(dirname(venv), exist_ok=True)
    commands = (
        ["/usr/bin/python3", "-m", "venv", venv],
        [f"{venv}/bin/pip", "install", "dns-lexicon[full]"],
    )
    if any(run_command(command)[0] for command in commands):
        return False
    return bool(which("turnkey-lexicon") and isfile(f"{venv}/bin/lexicon"))


def initial_setup() -> bool:
    venv = "/usr/local/src/venv/lexicon"
    if exists(f"{venv}/bin/lexicon") and exists(f"{venv}/bin/activate"):
        return True
    ret = console.yesno(
        "DNS validation needs the Lexicon tool. Install it now?", autosize=True
    )
    if ret != "ok":
        return False
    print("Installing the DNS validation tool. This can take a few minutes.")
    try:
        installed = install_lexicon()
    except OSError:
        installed = False
    if not installed:
        console.msgbox(
            "Could not install the DNS validation tool",
            "Check internet access and available disk space, then try again.",
            autosize=True,
        )
    return installed


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
