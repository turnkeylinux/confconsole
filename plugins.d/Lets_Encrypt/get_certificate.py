"""Get Let's Encrypt SSl cert"""

from executil import getoutput, ExecError
from os import path, remove

TITLE = 'Certificate Creation Wizard'

DESC = """Please enter domain to generate certificate for.

To generate a certificate for a single domain name, please enter it into the
first box and leave the others blank"

To generate a certificate for a base domain and a number of subdomains,
please enter the full domain first, then the subdomains on subsequent lines.

For advanced useage, please see:
https://www.turnkeylinux.org/docs/letsencrypt#advanced
"""

domain_path = '/etc/dehydrated/confconsole.domains.txt'
dehydrated_conf = '/etc/dehydrated'
default_domains = '''
# please use this file with confconsole or
# alternatively use dehydrated with it's appropriate
# configuration directly
''' 

# XXX Debug paths

def load_domains():
    ''' Loads domain conf, writes default config if non-existant. Expects
    "/etc/dehydrated" to exist '''
    if not path.isfile(domain_path):
        with open(domain_path, 'w') as fob:
            fob.write(default_domains+\
                    'example.com www.example.com ftp.example.com\n')
        return ['example.com', 'www.example.com', 'ftp.example.com', '', '']
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
        fob.write(default_domains + ' '.join(domains))

def invalid_domains(dom, subdoms):
    ''' Validates well known limitations of domain-name specifications
    doesn't enforce when or if special characters are valid. Returns a
    string if domains are invalid explaining why otherwise returns False'''
    if len(dom) > 254:
        return 'Domain names must not exceed 254 characters'
    for part in dom.split('.'):
        if not 0 < len(part) < 64:
            return ('Domain segments may not be larger than 63 characters'
                    'or less than 1')
    for subdom in subdoms:
        if subdom and not subdom.endswith(dom):
            return '{} is not a subdomain of {}'.format(subdom, dom)
        if len(subdom) > 254:
            return ('Domain names must not exceed 254 characters')
        for part in subdom.split('.'):
            if not len(part) < 64:
                return 'Domain segments may not be larger than 63 characters'
    return False


def run():
    field_width = 60
    field_names = ['domain', 'subdomain1', 'subdomain2', 'subdomain3', 'subdomain4']


    canceled = False

    ret = console.yesno(
        'DNS must be configured before obtaining certificates. '
        'Incorrectly configured dns and excessive attempts could '
        'lead to being temporarily blocked from requesting '
        'certificates.\n\nDo you wish to continue?',
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
    m = invalid_domains(domains[0], domains[1:])
    
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
                ('Domain', values[0], field_width, 255),
                ('Subdomain 1', values[1], field_width, 255),
                ('Subdomain 2', values[2], field_width, 255),
                ('Subdomain 3', values[3], field_width, 255),
                ('Subdomain 4', values[4], field_width, 255),
            ]
            ret, values = console.form(TITLE, DESC, fields, autosize=True)

            if ret != 0:
                canceled = True
                break

            msg = invalid_domains(values[0], values[1:])
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

