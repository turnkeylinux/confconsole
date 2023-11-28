#!/usr/bin/python3
import sys
import subprocess
import re

from subprocess import PIPE
from os import makedirs
from os.path import join, exists, dirname
from shutil import which

from typing import Optional

LEXICON_CONF = '/usr/share/confconsole/letsencrypt/lexicon.yml'

LEXICON_CONF_NOTE = '''# Configure according to lexicon documentation https://dns-lexicon.readthedocs.io/
# Note that documentation began around v.3.3.28 of lexicon. Therefore not all of
# the features might be available to you!
'''

LEXICON_CONF_MAX_LINES = 7

def load_config():
    ''' Loads lexicon config if present '''
    config = []
    if not path.isfile(LEXICON_CONF):
        while len(config) < LEXICON_CONF_MAX_LINES:
            config.append('')
        return config
    else:
        with open(LEXICON_CONF, 'r') as fob:
            for line in fob:
                line = line.rstrip()
                if line and not line.startswith('#'):
                    config.append(line)

        while len(config) > LEXICON_CONF_MAX_LINES:
            config.pop()
        while len(config) < LEXICON_CONF_MAX_LINES:
            config.append('')
        return config

def run_command(command: list[str]) -> tuple[int, str]:
    proc = subprocess.run(command)
    if proc.returncode != 0:
        com = ' '.join(command)
        return (proc.returncode,
                "Something went wrong when running {com} '{com.stderr}'")
    else:
        return 0, 'success'


def apt_install(pkgs: list[str]) -> tuple[int, str]:
    """Takes a list of package names, returns tuple(exit_code, message)"""
    for command in [['apt-get', 'update'],
                    ['apt-install', *pkgs, '-y']]:
        exit_code, string = run_command(command)
        if exit_code != 0:
            return exit_code, string
    return exit_code, string


def check_pkg(pkg: str) -> tuple[int, str]:
    """Takes a package name and returns True if installed, otherwise False"""
    p = subprocess.run(['apt-cache', 'policy', pkg],
                       capture_output=True, text=True)
    for line in p.stdout.split('\n'):
        line = line.strip()
        if line.startswith('Installed'):
            if not line.endswith('(none)'):
                return (1, "exectualbe in /usr/bin/ found but lexicon package"
                              " not installed!")
            else:
                return (0, "but (incompatible) Debian package detected -"
                           " removing and installing from upstream.")
    return (1,
            f"No apt policy results; package {pkg} may not be installable?")


def save_config(config: str) -> None:
    ''' Saves lexicon configuration '''
    with open(LEXICON_CONF, 'w') as fob:
        fob.write(LEXICON_CONF_NOTE)
        for line in config:
            line = line.rstrip()
            if line:
                fob.write(line + '\n')


def initial_setup() -> None:
    '''Check lexicon and deps are installed and ready to go

    Returns a tuple of exit code (0 = success) and message
    '''
    msg_start = 'lexicon tool is required for dns-01 challenge, '
    msg_mid = ''
    msg_end = '\n\nDo you wish to continue?'
    msg = ''
    remove_lexicon = False
    install_venv = False

    lexicon_bin = which('lexicon')
    venv = '/usr/local/src/venv/lexicon'
    lexicon_venv_bin = join(venv, 'bin/lexicon')
    if not lexicon_bin:
        # lexicon not found - install via venv
        install_venv = True
        msg_mid = "however it is not found on your system, so installing."
    elif exists(lexicon_venv_bin) and lexicon_bin == lexicon_venv_bin:
        # lexicon venv found - seems good to go
        msg = msg_start + "lexicon appears to be installed to venv, continuing"
    elif lexicon_bin == '/usr/bin/lexicon' and check_pkg('lexicon'):
        # lexicon pkg installed - remove and install via venv
        install_venv = True
        remove_lexicon = True
        msg_mid = ("lexicon deb install noted, but we need a newer version"
                   " removing deb and install via venv.")
    if not msg:
        msg = msg_start + msg_mid + msg_end
    ret = console.yesno(msg, autosize=True)
    if ret != 'ok':
        return
    if remove_lexicon:
        exit_code, msg = run_command(['apt-get', 'remove', '-y', 'lexicon'])
        if exit_code != 0:
            console.msgbox(
                'Error',
                f"Removal of lexicon package failed:\n\n{msg}")
    if install_venv:
        pkgs = []
        pip = which('pip')
        python3_venv = check_pkg('python3-venv')
        if not pip:
            pkgs.append('pip')
        if not python3_venv:
            pkgs.append('python3-venv')
        if pkgs:
            exit_code, msg = apt_install(pkgs)
            if exit_code != 0:
                pkgs_l = " ".join(pkgs)
                console.msgbox(
                    'Error',
                    f"Apt installing {pkgs_l} failed:\n\n{msg}")
        pip = which('pip')
        makedirs(dirname(venv), exist_ok=True)
        local_bin = '/usr/local/bin'
        for command in [
                ['python3', '-m', 'venv', venv],
                [pip, 'install', 'dns-lexicon[full]'],
                ['ln', '-s', f"{venv}/bin/lexicon", f"{local_bin}/lexicon"],
                ['ln', '-s', f"{venv}/bin/tldextract", f"{local_bin}/tldextract"]
                ]:
            assert isinstance(command, list)
            exit_code, msg = run_command(command)
            if exit_code != 0:
                com = " ".join(command)
                console.msgbox(
                    'Error',
                    f"Command '{com}' failed:\n\n{msg}")

        lexicon_bin = which('lexicon')
        lexicon_loc = '/usr/local/bin/lexicon'
        if lexicon_bin:
            if lexicon_bin != lexicon_loc:
                console.msgbox(
                    'Error',
                    "lexicon ({lexicon_bin}) not found where expected ({lexicon_loc})?!")
            else:
                return None
        console.msgbox('Error', "Something went wrong... Please report to TurnKey.")


def get_providers() -> tuple[Optional[list[tuple[str, str]]], Optional[str]]:
    lexicon_bin = which('lexicon')
    if not lexicon_bin:
        return None, 'lexicon is not found on your system, is it installed?'

    proc = subprocess.run([lexicon_bin, '--help'],
                          encoding=sys.stdin.encoding,
                          capture_output=True)
    if proc.returncode != 0:
        return None, proc.stderr.strip()

    match = re.search(r"(?<={).*(?=})", proc.stdout.strip())
    if not match:
        return None, 'Could not obtain DNS providers list from lexicon!'

    providers = []
    for provider in match.group().split(','):
        if len(provider) > 0:
            providers.append((provider, f'{provider} provider'))

    if providers:
        return providers, None
    return None, 'DNS providers list is empty!'
