"""Get Let's Encrypt SSl cert"""

import requests
import sys
import subprocess

from subprocess import PIPE
from os import path, remove
from shutil import copyfile, which
from json import JSONDecodeError
from glob import glob
from typing import Optional

LE_INFO_URL = 'https://acme-v02.api.letsencrypt.org/directory'

TITLE = 'Certificate Creation Wizard'

DESC = """Please enter domain(s) to generate certificate for.

To generate a single certificate for up to five domains (including subdomains),
enter each domain into a box, one domain per box. Empty boxes will be ignored.

Note that wildcard domains are supported, but only when using DNS-01 challenge
type.

To generate multiple certificates, please consult the advanced docs:
https://www.turnkeylinux.org/docs/letsencrypt#advanced
"""

dehydrated_conf = '/etc/dehydrated'
domain_path = path.join(dehydrated_conf, 'confconsole.domains.txt')
d_conf_path = path.join(dehydrated_conf, 'confconsole.config')
d_conf_example = '/usr/share/confconsole/letsencrypt/dehydrated-confconsole.config'

default_domains = '''# please use this file with confconsole or
# alternatively use dehydrated with it's appropriate
# configuration directly
'''
example_domain = 'example.com'
# XXX Debug paths

def doOnce():
    global dns_01
    dns_01 = impByPath('Lets_Encrypt/dns_01.py')

def read_conf(path: str) -> list[str]:
    """Read config from path and return as a list (line to an item)"""
    with open(path) as fob:
        return fob.read().split('\n')

def write_conf(conf: list[str]) -> None:
    """Writes (list of) config lines to dehydated conf path"""
    with open(d_conf_path, 'w') as fob:
        for line in conf:
            fob.write(line.rstrip() + '\n')

def update_conf(conf: list[str], new_values: dict[str, str]) -> list[str]:
    """Given a list of conf lines, lines which match keys from new_values
    {K: V} will be updated to 'K=V' - if K does not exist, will be ignored"""
    new_conf = []
    new_val_keys = list(new_values.keys())
    for line in conf:
        if line is None:
            continue
        if '=' in line and not line.startswith('#'):
            key = line.split('=', 1)[0]
            if key in new_val_keys:
                line = f'{key}="{new_values[key]}"'
        new_conf.append(line)
    write_conf(new_conf)
    return new_conf

def get_conf_value(conf: list[str], key: str) -> str:
    """Given a list of config lines and a key, returns the (first) corresponding
    value (non case sensititive). If nothing found, returns empty string.
    """
    for line in conf:
        if line is None:
            continue
        if '=' in line and not line.startswith('#'):
            if key.lower() == line.split('=', 1)[0].lower:
                return line.split('=', 1)[1].strip('"').strip("'")
    return ''

def initial_load_conf(provider: Optional[str] = None) -> list[str]:
    """Create or update Dehydrated conf file, if not passed provider, assumes
    http-01 challenge, otherwise assume dns-01. Also returns conf as list of
    lines"""
    src = d_conf_path
    if not path.exists(d_conf_path):
        src = d_conf_example
    conf = read_conf(src)
    if provider is None:  # assume http-01
        new_conf = {'CHALLENGETYPE': 'http-01'}
    else: # assume dns-01
        new_conf = {'CHALLENGETYPE': 'dns-01',
                    'PROVIDER': provider}
    conf = update_conf(conf, new_conf)
    write_conf(conf)
    return conf


def load_domains():
    ''' Loads domain conf, writes default config if non-existant. Expects
    "/etc/dehydrated" to exist '''
    if not path.isfile(domain_path):
        return [example_domain, '', '', '', '']
    else:
        backup_domain_path = '.'.join([domain_path, 'bak'])
        copyfile(domain_path, backup_domain_path)
        domains = []
        with open(domain_path, 'r') as fob:
            for line in fob:
                line = line.strip()
                if line and not line.startswith('#'):
                    domains = line.split(' ')
                    break

        while len(domains) > 5:
            domains.pop()
        while len(domains) < 5:
            domains.append('')
        return domains


def save_domains(domains):
    ''' Saves domain configuration '''
    with open(domain_path, 'w') as fob:
        fob.write(default_domains + ' '.join(domains) + '\n')


def invalid_domains(domains, challenge):
    ''' Validates well known limitations of domain-name specifications
    doesn't enforce when or if special characters are valid. Returns a
    string if domains are invalid explaining why otherwise returns False'''
    if domains[0] == '':
        return (f'Error: At least one domain must be provided in'
                ' {domain_path} (with no preceeding space)')
    for domain in domains:
        if len(domain) != 0:
            if len(domain) > 254:
                return (f'Error in {domain}: Domain names must not exceed 254'
                        ' characters')
            if domain.count('.') < 1:
                return (f'Error in {domain}: Domain may not have less'
                        ' than 2 segments')
            for part in domain.split('.'):
                if not 0 < len(part) < 64:
                    return (f'Error in {domain}: Domain segments may not be'
                            ' larger than 63 characters or less than 1')
        elif domain.startswith('*') and challenge.startswith('http'):
            return (f'Error in {domain}: Wildcard domains are only valid with'
                    ' DNS-01 challenge')
    return False


def run():
    field_width = 60
    field_names = ['domain1', 'domain2', 'domain3', 'domain4', 'domain5']

    canceled = False

    tos_url = None
    try:
        response = requests.get(LE_INFO_URL)
        tos_url = response.json()['meta']['termsOfService']
    except ConnectionError:
        msg = 'Connection error. Failed to connect to '+LE_INFO_URL
    except JSONDecodeError:
        msg = 'Data error, no JSON data found'
    except KeyError:
        msg = 'Data error, no value found for "terms-of-service"'
    if not tos_url:
        console.msgbox('Error', msg, autosize=True)
        return

    ret = console.yesno(
        "Before getting a Let's Encrypt certificate, you must agree"
        ' to the current Terms of Service.\n\n'
        'You can find the current Terms of Service here:\n\n'
        + tos_url + '\n\n'
        "Do you agree to the Let's Encrypt Terms of Service?",
        autosize=True
        )
    if ret != 'ok':
        return

    if not path.isdir(dehydrated_conf):
        console.msgbox(
            'Error',
            f'Dehydrated not installed or {dehydrated_conf} not found,'
            ' dehydrated can be installed via apt from the Debian repos.\n\n'
            'More info: www.turnkeylinux.org/docs/letsencrypt',
            autosize=True
        )
        return

    ret, challenge = console.menu(
            'Challenge type',
            'Select challenge type to use',
            [('http-01', 'Requires public web access to this system'),
             ('dns-01', 'Requires your DNS provider to provide an API')
             ])
    if ret != 'ok':
        return

    if challenge == 'http-01':
        ret = console.yesno(
            'DNS must be configured before obtaining certificates.'
            ' Incorrectly configured DNS and excessive attempts could'
            ' lead to being temporarily blocked from requesting'
            ' certificates.\n\n'
            "You can check for a valid 'A' DNS record for your domain via"
            ' Google:\n    https://toolbox.googleapps.com/apps/dig/\n\n'
            'Do you wish to continue?',
            autosize=True
        )
        if ret != 'ok':
            return
        d_conf = initial_load_conf()
        write_conf(d_conf)

    elif challenge == 'dns-01':
        dns_01.initial_setup()
        l_conf_possible = glob(path.join(dns_01.LEXICON_CONF_DIR, 'lexicon_*.yml'))
        if len(l_conf_possible) == 0:
            conf = None
        elif len(l_conf_possible) == 1:
            conf = l_conf_possible[0]
        elif len(l_conf_possible) >= 2:
            console.msgbox('Error',
                           "Multiple lexicon_*.yml conf files found in"
                           f" {LEXICON_CONF_DIR}, please ensure there is only"
                           " one",
                           autosize=True)
            return

        if conf:
            provider = path.basename(conf).split('_', 1)[1][:-4]
        else:
            providers, err = dns_01.get_providers()
            if err:
                console.msgbox('Error', err, autosize=True)
                return

            ret, provider = console.menu(
                    'DNS providers list',
                    "Select DNS provider you'd like to use",
                    providers)
            if ret != 'ok':
                return

            if provider == 'auto' and not which('nslookup'):
                ret = console.yesno(
                    'nslookup tool is required to use dns-01 challenge with'
                    ' auto provider.\n\n'
                    'Do you wish to install it now?',
                    autosize=True
                    )
                if ret != 'ok':
                    return
                return_code, message = dns_01.apt_install(['dnsutils'])
                if returncode != 0:
                    console.msgbox('Error', message, autosize=True)
                    return
            if not provider:
                console.msgbox('Error', 'No provider selected', autosize=True)

        d_conf = initial_load_conf(provider)
        conf_file, config = dns_01.load_config(provider)
        if len(config) > 12:
            console.msgbox(
                    'Error',
                    "Config file too big - needs to be 12 lines or less",
                    autosize=True)
            return
        elif len(config) < 12:
            for i in range(12 - len(config)):
                config.append('')
        fields = [
            ('', 1, 0, config[0], 1, 10, field_width, 255),
            ('', 2, 0, config[1], 2, 10, field_width, 255),
            ('', 3, 0, config[2], 3, 10, field_width, 255),
            ('', 4, 0, config[3], 4, 10, field_width, 255),
            ('', 5, 0, config[4], 5, 10, field_width, 255),
            ('', 6, 0, config[5], 6, 10, field_width, 255),
            ('', 7, 0, config[6], 7, 10, field_width, 255),
            ('', 8, 0, config[7], 8, 10, field_width, 255),
            ('', 9, 0, config[8], 9, 10, field_width, 255),
            ('', 10, 0, config[9], 10, 10, field_width, 255),
            ('', 11, 0, config[10], 11, 10, field_width, 255),
            ('', 12, 0, config[11], 12, 10, field_width, 255),

        ]
        ret, values = console.form(
                'Lexicon configuration',
                'Review and adjust current lexicon configuration as necessary.\n\n'
                'Please see https://www.turnkeylinux.org/docs/confconsole/letsencrypt#dns-01',
                fields,
                autosize=True)
        if ret != 'ok':
            return

        if config != values:
            dns_01.save_config(conf_file, values)


    domains = load_domains()
    m = invalid_domains(domains, challenge)

    if m:
        ret = console.yesno(
                (str(m) + '\n\nWould you like to ignore and overwrite data?'))
        if ret == 'ok':
            remove(domain_path)
            domains = load_domains()
        else:
            return

    values = domains

    while True:
        while True:
            fields = [
                ('Domain 1', 1, 0, values[0], 1, 10, field_width, 255),
                ('Domain 2', 2, 0, values[1], 2, 10, field_width, 255),
                ('Domain 3', 3, 0, values[2], 3, 10, field_width, 255),
                ('Domain 4', 4, 0, values[3], 4, 10, field_width, 255),
                ('Domain 5', 5, 0, values[4], 5, 10, field_width, 255),
            ]
            ret, values = console.form(TITLE, DESC, fields, autosize=True)

            if ret != 'ok':
                canceled = True
                break

            msg = invalid_domains(values, challenge)
            if msg:
                console.msgbox('Error', msg)
                continue

            if ret == 'ok':
                ret2 = console.yesno(
                        'This will overwrite any previous settings (saving a'
                        ' backup) and check for certificate. Continue?')
                if ret2 == 'ok':
                    save_domains(values)
                    break

        if canceled:
            break

        # User has accepted ToS as part of this process, so pass '--register'
        # switch to Dehydrated wrapper
        dehydrated_bin = ['bash', path.join(
                            path.dirname(PLUGIN_PATH), 'dehydrated-wrapper'),
                          '--register', '--log-info', '--challenge', challenge]
        if challenge == 'dns-01':
            dehydrated_bin.append('--provider')
            dehydrated_bin.append(provider)
        proc = subprocess.run(dehydrated_bin,
                              encoding=sys.stdin.encoding,
                              stderr=PIPE)
        if proc.returncode == 0:
            break
        else:
            console.msgbox('Error!', proc.stderr)
