"""Get Let's Encrypt SSl cert"""

import requests
from executil import getoutput, ExecError
from os import path, remove

LE_INFO_URL = 'https://acme-v01.api.letsencrypt.org/directory'

TITLE = 'Certificate Creation Wizard'

DESC = """Please enter domain(s) to generate certificate for.

To generate a single certificate for up to five domains (including subdomains),
enter each domain into a box, one domain per box. Empty boxes will be ignored.

To generate multiple certificates, please consult the advanced docs:
https://www.turnkeylinux.org/docs/letsencrypt#advanced
"""

dehydrated_conf = '/etc/dehydrated'
domain_path = dehydrated_conf+'/confconsole.domains.txt'

default_domains = '''# please use this file with confconsole or
# alternatively use dehydrated with it's appropriate
# configuration directly
'''
example_domain = 'example.com'
# XXX Debug paths

def load_domains():
    ''' Loads domain conf, writes default config if non-existant. Expects
    "/etc/dehydrated" to exist '''
    if not path.isfile(domain_path):
        return [example_domain, '', '', '', '']
    else:
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

def invalid_domains(domains):
    ''' Validates well known limitations of domain-name specifications
    doesn't enforce when or if special characters are valid. Returns a
    string if domains are invalid explaining why otherwise returns False'''
    if domains[0] == '':
        return ('Error: At least one domain must be provided in {} (with no'
            ' preceeding space)'.format(domain_path))
    for domain in domains:
        if len(domain) != 0:
            if len(domain) > 254:
                return ('Error in {}: Domain names must not exceed 254'
                    ' characters'.format(domain))
            for part in domain.split('.'):
                if not 0 < len(part) < 64:
                    return ('Error in {}: Domain segments may not be larger'
                        ' than 63 characters or less than 1'.format(domain))
    return False

def run():
    field_width = 60
    field_names = ['domain1', 'domain2', 'domain3', 'domain4', 'domain5']

    canceled = False

    tos_url = None
    try:
        response = requests.get(LE_INFO_URL)
        tos_url = response.json()['meta']['terms-of-service']
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
        'DNS must be configured before obtaining certificates. '
        'Incorrectly configured dns and excessive attempts could '
        'lead to being temporarily blocked from requesting '
        'certificates.\n\nDo you wish to continue?',
        autosize=True
    )
    if ret:
        return

    ret = console.yesno(
        "Before getting a Let's Encrypt certificate, you must agree "
        'to the current Terms of Service.\n\n'
        'You can find the current Terms of Service here:\n\n'
        +tos_url+'\n\n'
        "Do you agree to the Let's Encrypt Terms of Service?",
        autosize=True
    )
    if ret:
        return

    if not path.isdir(dehydrated_conf):
        console.msgbox(
            'Error',
            'Dehydrated not installed or %s not found, dehydrated can be installed with apt from the jessie-backports repo.\n\nMore info: www.turnkeylinux.org/docs/letsencrypt' % dehydrated_conf,
            autosize=True
        )
        return

    domains = load_domains()
    m = invalid_domains(domains)
    
    if m:
        ret = console.yesno(
                (str(m) + '\n\nWould you like to ignore and overwrite data?'))
        if not ret:
            remove(domain_path)
            domains = load_domains()
        else:
            return

    values = domains

    while True:
        while True:
            fields = [
                ('Domain 1', values[0], field_width, 255),
                ('Domain 2', values[1], field_width, 255),
                ('Domain 3', values[2], field_width, 255),
                ('Domain 4', values[3], field_width, 255),
                ('Domain 5', values[4], field_width, 255),
            ]
            ret, values = console.form(TITLE, DESC, fields, autosize=True)

            if ret != 0:
                canceled = True
                break

            msg = invalid_domains(values)
            if msg:
                console.msgbox('Error', msg)
                continue

            if ret is 0:
                ret2 = console.yesno('This will overwrite previous settings and check for certificate, continue?')
                if ret2 is 0:
                    save_domains(values)
                    break


        if canceled:
            break

        try:
            getoutput('bash {}'.format(path.join(path.dirname(PLUGIN_PATH), 'dehydrated-wrapper')))
            break
        except ExecError as err:
            _, _, errmsg = err.args
            console.msgbox('Error!', errmsg)

