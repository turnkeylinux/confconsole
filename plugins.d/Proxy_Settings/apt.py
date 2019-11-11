''' Set APT's HTTP Proxy '''
from re import match, sub, MULTILINE, search
from os.path import isfile
import urllib.parse
from urllib.parse import urlparse

CONF = '/etc/apt/apt.conf.d/80proxy'
PROXY_LINE = r'Acquire::http::Proxy "(.*)";'
PROXY_REPL = r'Acquire::http::Proxy "{}";'


def get_proxy():
    proxy = ''
    if not isfile(CONF):
        return proxy
    with open(CONF, 'rb') as fob:
        for line in fob:
            lmatch = match(PROXY_LINE, line)
            if lmatch:
                proxy = lmatch.group(1)
    return proxy


def set_proxy(prox):
    if isfile(CONF):
        with open(CONF, 'rb') as fob:
            data = fob.read()
    else:
        data = ''

    if search(PROXY_LINE, data):
        data = sub(PROXY_LINE, PROXY_REPL.format(prox), data, 1, MULTILINE)
    else:
        data += '\n' + (PROXY_REPL.format(prox)) + '\n'

    with open(CONF, 'wb') as fob:
        fob.write(data)


def validate_address(addr):
    parsed = urlparse(addr)
    return parsed.scheme and len(parsed.netloc.split('.')) > 1


def doOnce():
    pass


def run():
    original_proxy = get_proxy()
    while True:
        prox = console.inputbox(
                'Set proxy',
                'Set a HTTP Proxy. Must contain scheme "http://example.com"'
                ' but not "example.com"',
                init=original_proxy)
        if prox[0] == 0:
            if prox[1] and not validate_address(prox[1]):
                console.msgbox(
                        'Invalid Proxy',
                        'A valid proxy address must at least have a net'
                        ' location and scheme (http://example.com) but not'
                        ' (example.com)')
            else:
                if not prox[1] and original_proxy:
                    # if no proxy chosen but there WAS a proxy set previously
                    if console.yesno('Are you sure you want to disable apt'
                                     ' proxy?') == 0:
                        set_proxy(prox[1])
                else:
                    set_proxy(prox[1])
                break
        else:
            break
