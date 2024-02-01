''' Set APT's HTTP Proxy '''
from re import match, sub, MULTILINE, search
from os.path import isfile
from urllib.parse import urlparse

CONF = '/etc/apt/apt.conf.d/80proxy'
PROXY_LINE = r'Acquire::http::Proxy "(.*)";'
PROXY_REPL = r'Acquire::http::Proxy "{}";'


def get_proxy():
    proxy = ''
    if not isfile(CONF):
        return proxy
    with open(CONF, 'r') as fob:
        for line in fob:
            lmatch = match(PROXY_LINE, line)
            if lmatch:
                proxy = lmatch.group(1)
    return proxy


def set_proxy(prox):
    if isfile(CONF):
        with open(CONF, 'r') as fob:
            data = fob.read()
    else:
        data = ''

    if search(PROXY_LINE, data):
        data = sub(PROXY_LINE, PROXY_REPL.format(prox), data, 1, MULTILINE)
    else:
        data += '\n' + (PROXY_REPL.format(prox)) + '\n'

    with open(CONF, 'w') as fob:
        fob.write(data)


def validate_address(addr):
    parsed = urlparse(addr)
    return parsed.scheme and len(parsed.netloc.split('.')) > 1


def doOnce():
    pass


def run():
    original_proxy = get_proxy()
    while True:
        # console is inherited so doesn't need to be defined
        code, prox = console.inputbox(  # type: ignore[not-defined]
                'Set proxy',
                'Set a HTTP Proxy. Must contain scheme "http://example.com"'
                ' but not "example.com"',
                init=original_proxy)
        if code == 'ok':
            if prox and not validate_address(prox):
                console.msgbox(  # type: ignore[not-defined]
                        'Invalid Proxy',
                        'A valid proxy address must at least have a net'
                        ' location and scheme (http://example.com) but not'
                        ' (example.com)')
            else:
                if not prox and original_proxy:
                    # if no proxy chosen but there WAS a proxy set previously
                    if console.yesno(  # type: ignore[not-defined]
                            'Are you sure you want to disable apt proxy?'
                            ) == 'ok':
                        set_proxy(prox)
                else:
                    set_proxy(prox)
                break
        else:
            break
