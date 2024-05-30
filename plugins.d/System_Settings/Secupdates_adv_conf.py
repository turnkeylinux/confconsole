"""Config SecUpdate behaviour"""

import os
from os.path import exists, islink
from typing import Optional

FILE_PATH = '/etc/cron-apt/action.d/5-install'
CONF_DEFAULT = '/etc/cron-apt/action-available.d/5-install.default'
CONF_ALT = '/etc/cron-apt/action-available.d/5-install.alt'

doc_url = 'www.turnkeylinux.org/docs/auto-secupdates#issue-res'

info_default = """
This is the historic and default TurnKey cronapt behaviour. Only packages \
from the repos listed in security.sources.list will be installed. \
Missing dependencies will not be installed and will cause package removal. \
This package removal may cause one or more services to fail."""

info_alternate = """
This is a new option which is similar to the default. However, it will not \
allow removal of packages. This will maximise uptime of all services, but \
conversely, may also allow services with unpatched security vulnerabilities \
to continue running."""


def new_link(link_path: str, target_path: str) -> None:
    try:
        os.unlink(link_path)
    except FileNotFoundError:
        pass
    os.symlink(link_path, target_path)


def conf_default() -> None:
    new_link(FILE_PATH, CONF_DEFAULT)


def conf_alternate() -> None:
    new_link(FILE_PATH, CONF_ALT)


def check_paths() -> tuple[int, list[str]]:
    errors: list[str] = []
    for _path in [FILE_PATH, CONF_DEFAULT, CONF_ALT]:
        if not exists(_path):
            errors.append(f'Path not found: {_path}')
    if errors:
        return 2, errors
    if islink(FILE_PATH):
        _target_path = os.readlink(FILE_PATH)
        if _target_path.startswith('../action-available.d/5-install'):
            _target_path = _target_path.replace('..', '/etc/cron-apt')
        if _target_path == CONF_DEFAULT:
            return 0, ['default']
        elif _target_path == CONF_ALT:
            return 0, ['alternate']
        else:
            return 1, [f'Unexpected link target: {_target_path}']
    else:
        return 1, [f'{FILE_PATH} is not a symlink']


def button_label(current: str) -> str:
    options = ['default', 'alternate']
    try:
        options.remove(current)
    except ValueError:
        pass

    other = options[0]
    msg = f"Enable '{other}'"

    return f"{msg:^20}"


def get_details(choice: str) -> Optional[str]:
    if choice == 'default':
        return info_default
    elif choice == 'alternate':
        return info_alternate
    else:
        return None


def run() -> None:
    retcode, data = check_paths()
    if retcode:
        msg = ('Error(s) encountered while checking status:')
        for message in data:
            msg = f'{msg}\n\t{message}'
        msg = (f'{msg}\nFor more info please see\n\n{doc_url}')
        r = console.msgbox('Error', msg)  # type: ignore[name-defined]
    else:
        # if retcode == 0, then data == [status]
        status = data[0]
        msg = ('Current SecUpate Issue resolution strategy is:\n\n\t{}'
               '\n{}\n\nFor more info please see\n\n{}')
        r = console._wrapper('yesno',  # type: ignore[name-defined]
                             msg.format(status, get_details(status), doc_url),
                             20, 60,
                             yes_label=button_label(status),
                             no_label='Back')
        while r == 'ok':
            # Toggle was clicked
            if data == ['default']:
                conf_alternate()
            else:
                conf_default()
            retcode, data = check_paths()
            status = data[0]
            r = console._wrapper('yesno',  # type: ignore[name-defined]
                                 msg.format(status,
                                            get_details(status),
                                            doc_url),
                                 20, 60,
                                 yes_label=button_label(status),
                                 no_label='Back')
