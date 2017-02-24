"""Enable/Disable auto-renew cronjob"""

from os import chmod, stat

CRON_PATH='/etc/cron.weekly/confconsole-dehydrated'

def enable_cron():
    st = stat(CRON_PATH)
    chmod(CRON_PATH, st.st_mode | 0o111)

def disable_cron():
    st = stat(CRON_PATH)
    chmod(CRON_PATH, st.st_mode ^ 0o111)

def check_cron():
    st = stat(CRON_PATH)
    return st.st_mode & 0o111 == 0o111

def run():
    enabled = check_cron()
    status = 'enabled' if enabled else 'disabled'
    msg = '''Automatic certificate renewal is currently {}''' 
    r = console._wrapper('yesno', msg.format(status), 10, 30, yes_label='Toggle', no_label='Ok')
    while r == 0:
        if enabled:
            disable_cron()
        else:
            enable_cron()
        enabled = check_cron()
        status = 'enabled' if enabled else 'disabled'
        r = console._wrapper('yesno', msg.format(status), 10, 30, yes_label='Toggle', no_label='Ok') 
