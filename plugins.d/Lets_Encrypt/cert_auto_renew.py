"""Enable/Disable cert auto-renew"""

from os import chmod, stat, path

CRON_PATH = '/etc/cron.daily/confconsole-dehydrated'


def enable_cron():
    st = stat(CRON_PATH)
    chmod(CRON_PATH, st.st_mode | 0o111)


def disable_cron():
    st = stat(CRON_PATH)
    chmod(CRON_PATH, st.st_mode ^ 0o111)


def check_cron():
    if path.isfile(CRON_PATH):
        st = stat(CRON_PATH)
        return st.st_mode & 0o111 == 0o111
    else:
        return 'fail'


def run():
    enabled = check_cron()
    if enabled == 'fail':
        msg = ('Cron job for dehydrated does not exist.\n'
               'Please "Get certificate" first.')
        # console is inherited so doesn't need to be defined
        r = console.msgbox('Error', msg)  # type: ignore[not-defined]
    else:
        status = 'enabled' if enabled else 'disabled'
        msg = '''Automatic certificate renewal is currently {}'''
        r = console._wrapper('yesno',  # type: ignore[not-defined]
                             msg.format(status), 10, 30,
                             yes_label='Toggle', no_label='Ok')
        while r == 'ok':
            if enabled:
                disable_cron()
            else:
                enable_cron()
            enabled = check_cron()
            status = 'enabled' if enabled else 'disabled'
            r = console._wrapper('yesno',  # type: ignore[not-defined]
                                 msg.format(status), 10, 30,
                                 yes_label='Toggle', no_label='Ok')
