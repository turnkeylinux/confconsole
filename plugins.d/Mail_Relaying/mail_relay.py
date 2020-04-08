'''Setup relaying'''

import ssl
import socket
import sys
from smtplib import SMTP, SMTP_SSL, SMTPException
import os
import subprocess
from subprocess import PIPE

TITLE = 'Mail Relay'

TEXT = ('By default, TurnKey servers send e-mail directly. An SMTP relay'
        ' provides more robust mail deliverability.\n\n'
        'Send up to 9000 emails per month with a free SendinBlue account.'
        ' To sign up, open the below URL in your web browser and follow the'
        ' prompts:\n\n'
        'https://hub.turnkeylinux.org/email')

FORMNOTE = ("Please enter the settings below.\n\n"
            "Note: The relay authentication procedure requires the user"
            " password to be stored in plain text at /etc/postfix/sasl_passwd"
            " (readable only by root). If this is not what you want, you"
            " should cancel this configuration step.")


def testsettings(host, port, login, password):

    encoding = sys.stdin.encoding

    # login username and password must be string
    def bytes2string(string):
        if type(string) is bytes:
            return string.decode(encoding)
        return string

    host = host.encode(encoding)
    port = int(port)
    login = bytes2string(login)
    password = bytes2string(password)

    try:  # SSL
        smtp = SMTP_SSL(host, port)
        ret, msg = smtp.login(login, password)
        smtp.quit()

        if ret is 235:  # 2.7.0 Authentication successful
            return True, None
    except (ssl.SSLError, SMTPException):
        pass

    try:  # STARTTLS or plaintext
        smtp = SMTP(host, port)
        smtp.starttls()
        smtp.ehlo()
        ret, msg = smtp.login(login, password)
        smtp.quit()

        if ret is 235:
            return True, None
    except SMTPException as e:
        ret, msg = e.args[0], e.args[1].decode(encoding)
        pass

    return False, (ret, msg)


def run():
    host = 'localhost'
    port = '25'
    login = ''
    password = ''

    cmd = os.path.join(os.path.dirname(__file__), 'mail_relay.sh')

    retcode, choice = console.menu(TITLE, TEXT, [
        ('SendinBlue', "TurnKey's preferred SMTP gateway"),
        ('Custom', 'Custom mail relay configuration'),
        ('Deconfigure', 'Erase current mail relay settings')
    ])

    if choice:
        if choice == 'Deconfigure':
            proc = subprocess.run([cmd, 'deconfigure'],
                                  encoding=sys.stdin.encoding,
                                  stderr=PIPE)
            if proc.returncode != 0:
                console.msgbox('Error', proc.stderr)
                return

            console.msgbox(TITLE,
                           'The mail relay settings were succesfully erased.'
                           ' No relaying will take place from now on.')
            return

        if choice == 'SendinBlue':
            host = 'smtp-relay.sendinblue.com'
            port = '587'

        field_width = field_limit = 100

        while 1:
            fields = [
                ('Host', 1, 0, host, 1, 10, field_width, field_limit),
                ('Port', 2, 0, port, 2, 10, field_width, field_limit),
                ('Login', 3, 0, login, 3, 10, field_width, field_limit),
                ('Password', 4, 0, password, 4, 10, field_width, field_limit)
            ]

            retcode, values = console.form(TITLE, FORMNOTE, fields)
            host, port, login, password = tuple(values)

            if retcode is not 'ok':
                console.msgbox(TITLE,
                               'You have cancelled the configuration process.'
                               ' No relaying of mail will be performed.')
                return

            elif not login:
                ret = console.yesno(
                        'No login username provided. Unable to test'
                        ' SMTP connection before configuring.\n\nAre you sure'
                        ' you want to configure SMTP forwarding with no login'
                        ' credentials?', autosize=True)
                if ret != 'ok':
                    return
                else:
                    break

            else:
                success, error_msg = testsettings(*values)
                if success:
                    console.msgbox(
                            TITLE,
                            'SMTP connection test successful.\n\n'
                            'Ready to configure Postfix.')
                    break

                else:
                    console.msgbox(
                            TITLE,
                            'Could not connect with supplied parameters.\n\n'
                            'Error code: {}\n\nMessage:\n\n  {}\n\nPlease'
                            ' check config and try again.'.format(*error_msg))
                    return

        proc = subprocess.run([cmd, host, port, login, password],
                              encoding=sys.stdin.encoding,
                              stderr=PIPE)
        if proc.returncode != 0:
            console.msgbox('Error', proc.stderr)
