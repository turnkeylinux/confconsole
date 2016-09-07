''' Set APT's HTTP Proxy '''
from re import match, sub, MULTILINE, search
from os.path import isfile

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
    
                

def doOnce():
    pass

def run():
    prox = console.inputbox('Set proxy', 'Set a HTTP Proxy', init = get_proxy())
    if prox[0] == 0:
        set_proxy(prox[1])
