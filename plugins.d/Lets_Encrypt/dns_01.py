#!/usr/bin/python3
import sys
import subprocess
import re

from os import makedirs, chmod, chown
from os.path import isfile, join, exists, dirname, realpath
from shutil import which, copy

from typing import Optional

LEXICON_SHARE_DIR = '/usr/share/confconsole/letsencrypt'
LEXICON_CONF_DIR = '/etc/dehydrated'

LEXICON_CONF_NOTE = '''# Configure according to lexicon documentation https://dns-lexicon.readthedocs.io/
#
'''

#LEXICON_CONF_MAX_LINES = 7

def load_config(provider: str) -> tuple[str, list[str]]:
    ''' Loads lexicon config if present, loads example if not,
    returns tuple(conf_file, list(config))'''
    if provider in ['route53', 'cloudflare']:
        example_conf = join(LEXICON_SHARE_DIR,
                            f'lexicon-confconsole-provider_{provider}.yml')
    else:
        example_conf = join(LEXICON_SHARE_DIR,
                            'lexicon-confconsole-provider_example.yml')
    conf_file = join(LEXICON_CONF_DIR, f'lexicon_{provider}.yml')
    config = []
    if not isfile(conf_file):
        copy(example_conf, conf_file)
        # ensure root read/write only as file contains sensitive info
        chown(conf_file, 0, 0) # chown root:root
        chmod(conf_file, 0o600) # chmod 600 (owner read/write only)
    with open(conf_file, 'r') as fob:
        for line in fob:
            config.append(line.rstrip())

    #    while len(config) > LEXICON_CONF_MAX_LINES:
    #       config.pop()
    #    while len(config) < LEXICON_CONF_MAX_LINES:
    #        config.append('')
    return conf_file, config


def save_config(conf_file: str, config: str) -> None:
    ''' Saves lexicon configuration '''
    with open(conf_file, 'w') as fob:
        fob.write(LEXICON_CONF_NOTE)
        for line in config:
            if line:
                fob.write(line.rstrip() + '\n')
    # ensure root read/write only as file contains sensitive info
    chown(conf_file, 0, 0) # chown root:root
    chmod(conf_file, 0o600) # chmod 600 (owner read/write only)


def run_command(command: list[str], env: Optional[dict[str, str]] = None
        ) -> tuple[int, str]:
    if env is None:
        env = {}
    proc = subprocess.run(command, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        com = ' '.join(command)
        return (proc.returncode,
                f"Something went wrong when running {com}:\n\n{proc.stderr}")
    else:
        return 0, 'success'


def apt_install(pkgs: list[str]) -> tuple[int, str]:
    """Takes a list of package names, returns tuple(exit_code, message)"""
    env = {'DEBIAN_FRONTEND': 'noninteractive'}
    for command in [['apt-get', 'update'],
                    ['apt-get', 'install', *pkgs, '-y']]:
        exit_code, string = run_command(command, env=env)
        if exit_code != 0:
            return exit_code, string
    return exit_code, string


def check_pkg(pkg: str) -> bool:
    """Takes a package name and returns True if installed, otherwise False"""
    p = subprocess.run(['apt-cache', 'policy', pkg],
                       capture_output=True, text=True)
    for line in p.stdout.split('\n'):
        line = line.strip()
        if line.startswith('Installed'):
            if not line.endswith('(none)'):
                return True # package installed
            else:
                return False # package probably available but not installed
    return False # package uninstallable


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
    lexicon_venv_bin_syml = '/usr/local/bin/lexicon'
    if not lexicon_bin:
        # lexicon not found - offer to install via venv
        install_venv = True
        msg_mid = "however it is not found on your system, so installing."
    elif (exists(lexicon_venv_bin) and exists(lexicon_venv_bin_syml)
            and realpath(lexicon_bin) == lexicon_venv_bin):
        # lexicon venv found - no message required
        msg = None
    elif lexicon_bin == '/usr/bin/lexicon' and check_pkg('lexicon'):
        # lexicon pkg installed - offer to remove and install via venv
        install_venv = True
        remove_lexicon = True
        msg_mid = ("lexicon deb install noted, but we need a newer version"
                   " removing deb and install via venv.")
    else:
        msg_mid = "but your system is in an unexpected state"
    if msg is not None:
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
            pkgs.append('python3-pip')
        if not python3_venv:
            pkgs.append('python3-venv')
        if pkgs:
            exit_code, msg = apt_install(pkgs)
            if exit_code != 0:
                pkgs_l = " ".join(pkgs)
                console.msgbox(
                    'Error',
                    f"Apt installing {pkgs_l} failed:\n\n{msg}")
        makedirs(dirname(venv), exist_ok=True)
        local_bin = '/usr/local/bin'
        venv_pip = join(venv, 'bin/pip')
        for command in [
                ['python3', '-m', 'venv', venv],
                [venv_pip, 'install', 'dns-lexicon[full]'],
                ['ln', '-sf', f"{venv}/bin/lexicon", f"{local_bin}/lexicon"],
                ['ln', '-sf', f"{venv}/bin/tldextract", f"{local_bin}/tldextract"]
            ]:
            assert isinstance(command, list)
            exit_code, msg = run_command(command)
            if exit_code != 0:
                com = " ".join(command)
                console.msgbox(
                    'Error',
                    f"Command '{com}' failed:\n\n{msg}")
                return None

        lexicon_bin = which('lexicon')
        lexicon_loc = '/usr/local/bin/lexicon'
        if lexicon_bin:
            if lexicon_bin != lexicon_loc:
                console.msgbox(
                    'Error',
                    f"lexicon ({lexicon_bin}) not found where expected ({lexicon_loc})?!")
            else:
                return None
        console.msgbox('Error', "Something went wrong... Please report to TurnKey.")
        return None


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
