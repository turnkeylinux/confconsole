'''Setup relaying'''

import ssl
import socket
from smtplib import SMTP, SMTP_SSL, SMTPException
from os import path, system

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
    host = host.encode('utf-8')
    port = int(port)
    login = login.encode('utf-8')
    password = password.encode('utf-8')

    try:  # SSL
        smtp = SMTP_SSL(host, port)
        ret, _ = smtp.login(login, password)
        smtp.quit()

        if ret is 235:  # 2.7.0 Authentication successful
            return True
    except (ssl.SSLError, SMTPException):
        pass

    try:  # STARTTLS or plaintext
        smtp = SMTP(host, port)
        smtp.starttls()
        smtp.ehlo()
        ret, _ = smtp.login(login, password)
        smtp.quit()

        if ret is 235:
            return True
    except SMTPException:
        pass

    return False


def run():
    host = 'localhost'
    port = '25'
    login = ''
    password = ''

    cmd = path.join(path.dirname(__file__), 'mail_relay.sh')

    retcode, choice = console.menu(TITLE, TEXT, [
        ('SendinBlue', "TurnKey's preferred SMTP gateway"),
        ('Custom', 'Custom mail relay configuration'),
        ('Deconfigure', 'Erase current mail relay settings')
    ])

    if choice:
        if choice == 'Deconfigure':
            system(cmd, 'deconfigure')
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
                ('Host', host, field_width, field_limit),
                ('Port', port, field_width, field_limit),
                ('Login', login, field_width, field_limit),
                ('Password', password, field_width, field_limit)
            ]

            retcode, values = console.form(TITLE, FORMNOTE, fields)

            if retcode is not 'ok':
                console.msgbox(TITLE,
                               'You have cancelled the configuration process.'
                               ' No relaying of mail will be performed.')
                return

            host, port, login, password = tuple(values)

            if testsettings(*values):
                break
            else:
                console.msgbox(TITLE,
                               'Could not connect with supplied parameters.'
                               ' Please check config and try again.')

        system(cmd, host, port, login, password)
