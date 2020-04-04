'''Regenerate DH parameters'''

import shutil
import os
from subprocess import Popen, PIPE

TITLE = 'Regenerate Diffie-Hellman parameters'

TEXT = ('SSL/TLS connections (e.g. HTTPS) use DH params. The default 1024 bit'
        ' file protects from most attackers, but not highly resourced ones'
        ' (e.g. nation-states). A min 2048 bit size is recommended. Bigger ='
        ' Better.\n\n'
        'Note: higher bit size generation is exponentially slower.'
        ' For more info see:\n\n'
        'https://www.turnkeylinux.org/docs/regen-dhparams')


def run():

    cmd = [os.path.join(os.path.dirname(__file__), 'regen_dhparams.sh')]

    retcode, dh_bits = console.menu(TITLE, TEXT, [
        ('1024', "Default - quick generation but not ideal"),
        ('2048', 'Slower - Slower to generate but more secure'),
        ('4096', 'Best - Will take hours; perhaps days!')
        ])

    if dh_bits:
        warning = ("Exiting confconsole (including hitting <Ctrl><C>, or a"
                   " dropped SSH connection) will interrupt the generation"
                   " process.\n\nIt is suggested that you run within a screen"
                   " (or similar) session. For more info, please see"
                   " https://www.turnkeylinux.org/docs/regen-dhparams")

        if dh_bits == '1024':

            note = ("{} is the default bit size and shouldn't take too long to"
                    " regenerate.")
            time = "won't take long"

        if dh_bits == '2048':

            note = ("{} bit will take a while to generate. At least a few"
                    " minutes, perhaps as long as 10 (or more on low spec"
                    " hardware).")
            time = "will take a while"

        if dh_bits == '4096':

            note = ("{} bit will take a LONG time to generate. It may take"
                    " hours. On low spec hardware, it could literally take"
                    " days!")
            time = "will take hours"

        note = note.format(dh_bits)
        yesno_msg = ("{}\n\n{}\n\nPlease note that there will be limited"
                     " feedback. Continue?".format(warning, note))
        ret = console.yesno(yesno_msg, autosize=True)

        if ret is not 'ok':
            console.msgbox(TITLE,
                           "You have cancelled the generation process. The DH"
                           " params file will remain unchanged.")
            return

        msg = ("Generating {} bit DH params file. Please wait - this {}...")
        print(msg.format(dh_bits, time))

        cmd.append(dh_bits)
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        log_content = []
        while True:
            output = proc.stdout.readline()
            if proc.poll() is not None:
                break
            if output:
                log_content.append(output)
                print(output.decode().strip())

        if proc.returncode != 0:
            log_dir = '/var/log/confconsole'
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            log_file = os.path.join(log_dir, 'gen_dhparams.error')
            with open(log_file, 'wb') as fob:
                fob.write(b''.join(log_content))
            console.msgbox(TITLE,
                           "Something went wrong!\n\nOutput has been written"
                           " to {}.".format(log_file))
        else:
            console.msgbox(TITLE,
                           "The generation process completed successfully.")
