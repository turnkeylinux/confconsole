"""Obtain a certificate from Let's Encrypt"""

from executil import getoutput, ExecError
from os import path

TITLE = 'Certificate Creation Wizard'

DESC = """
Please enter the values to use for the generated certificate.

The Common Name is most commonly the domain name you intend to use for your website.
"""

def run():
    field_width = 60
    field_names = ['C', 'ST', 'L', 'O', 'OU', 'CN']

    canceled = False

    if not path.isfile('/usr/bin/dehydrated'):
        console.msgbox(
            'Error',
            'Dehydrated not installed, please see www.turnkeylinux.org/docs/letsencrypt',
            autosize=True
        )
        return

    while True:
        while True:
            fields = [
                ('2-letter country code', '', 2, 2),
                ('State', '', field_width, field_width),
                ('Locality', '', field_width, field_width),
                ('Organization', '', field_width, field_width),
                ('Organizational Unit', '', field_width, field_width),
                ('Common Name', '', field_width, field_width)
            ]

            ret, values = console.form(TITLE, DESC, fields)

            if ret != 0:
                canceled = True
                break

            if values and len(values[0]) != 2:
                console.msgbox(TITLE, 'Country code is invalid.')
                continue

            if values and not len(values[5]):
                console.msgbox(TITLE, 'Common name is empty!')
                continue

            if ret is 0:
                break

        if canceled:
            break

        crtpath = path.join('/', 'etc', 'ssl', 'private', values[-1] + '.crt')
        ret, crtpath = console.inputbox(TITLE, 'You may edit the path where to generate the certificate and accompanying files if desired:', crtpath)

        basepath = path.splitext(crtpath)[0]
        keypath = basepath + '.key'
        csrpath = basepath + '.csr'

        subjline = '/' + '/'.join('%s=%s' % x for x in zip(field_names, values))

        try:
            getoutput('openssl', 'ecparam', '-out', keypath, '-name', 'prime256v1', '-genkey')
            getoutput('openssl', 'req', '-new', '-key', keypath, '-nodes', '-out', csrpath, '-subj', subjline)
            getoutput('/usr/bin/dehydrate', '--signcsr', csrpath, '--hook', '/usr/local/etc/letsencrypt.sh/hook.sh', '--out', basepath)

            break
        except ExecError as err:
            _, _, errmsg = err.args
            console.msgbox('Error!', errmsg)

