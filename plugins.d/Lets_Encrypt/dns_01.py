#!/usr/bin/python3
import sys
import subprocess
import re

from subprocess import PIPE
from os import path
from shutil import which

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

def save_config(config):
    ''' Saves lexicon configuration '''
    with open(LEXICON_CONF, 'w') as fob:
        fob.write(LEXICON_CONF_NOTE)
        for line in config:
            line = line.rstrip()
            if line:
                fob.write(line + '\n')

def get_providers():
    lexicon_bin = which('lexicon')
    if not lexicon_bin:
        ret = console.yesno(
            'lexicon tool is required to use dns-01 challenge, '
            'however it is not found on your system.\n\n'
            'Do you wish to install it now?',
            autosize=True
        )
        if ret != 'ok':
            return None, 'Please install lexicon to use dns-01 challenge.'

        apt = subprocess.run(['apt-get', '-y', 'install', 'lexicon'],
                             encoding=sys.stdin.encoding,
                             stderr=PIPE)
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
