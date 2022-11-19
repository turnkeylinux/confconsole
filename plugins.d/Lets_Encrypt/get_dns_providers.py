#!/usr/bin/python3
import sys
import subprocess
from subprocess import PIPE
from shutil import which
import re

def get_providers():
    lexicon_bin = which('lexicon')
    if not lexicon_bin:
        ret = console.yesno(
            'lexicon tool is required to use dns-01 challenge, '
            'however it is not found on your system.\n\n'
            'Would you like to install it now?',
            autosize=True
        )
        if ret != 'ok':
            return None, 'Please install lexicon to use dns-01 challenge.'

        apt = subprocess.run(['apt', '-y', 'install', 'lexicon'],
                             encoding=sys.stdin.encoding,
                             capture_output=True)
        if apt.returncode != 0:
            return None, apt.stderr.strip()

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
            providers.append((provider, '%s provider' % provider))

    if providers:
        return providers, None
    return None, 'DNS providers list is empty!'
