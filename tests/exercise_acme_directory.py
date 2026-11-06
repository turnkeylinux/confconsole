"""Drive the installed wizard in a disposable Docker guest; no settings saved."""

import os
from pathlib import Path
import subprocess
import time

import pexpect
import pyte

CONTAINER = os.environ.get('ACME_QA_CONTAINER', 'dns01-qa-20261106')
OUT = Path('acme-terminal-evidence')
OUT.mkdir(exist_ok=True)


def mode(value):
    subprocess.run(['sudo', 'docker', 'exec', CONTAINER, 'sh', '-c',
                    'printf "%s" "$1" > /root/acme-directory-qa/mode',
                    'sh', value], check=True)


def exercise(case, expected, columns=80, trust=True, refused=False):
    args = ['docker', 'exec', '-it', '-e', 'TERM=xterm', '-e',
            'HTTPS_PROXY=http://127.0.0.1:' + ('18999' if refused else '18998'),
            '-e', 'NO_PROXY=']
    if trust:
        args += ['-e', 'REQUESTS_CA_BUNDLE=/root/acme-directory-qa/cert.pem']
    args += [CONTAINER, 'confconsole', '--plugin=get certificate']
    child = pexpect.spawn('sudo', args, encoding='utf-8',
                          dimensions=(24, columns), timeout=25)
    screen = pyte.Screen(columns, 24)
    stream = pyte.Stream(screen)
    started = time.monotonic()
    deadline = started + 25
    while time.monotonic() < deadline:
        try:
            stream.feed(child.read_nonblocking(65536, timeout=0.2))
        except pexpect.TIMEOUT:
            pass
        view = '\n'.join(screen.display)
        assert 'Traceback' not in view
        if expected in view:
            (OUT / f'{columns}-{case}.txt').write_text(view+'\n')
            break
    else:
        (OUT / f'{columns}-{case}-timeout.txt').write_text(view+'\n')
        raise AssertionError('Expected dialog absent: '+case)
    elapsed = time.monotonic() - started
    child.send('\t\r' if case == 'success' else '\r')
    child.expect(pexpect.EOF)
    child.close()
    assert child.exitstatus == 0, child.exitstatus
    print(f'{columns} columns {case}: clean exit, dialog in {elapsed:.3f}s', flush=True)


for columns in (60, 80, 120):
    mode('success')
    exercise('untrusted-tls', 'TLS certificate', columns, trust=False)
    # The user's retry uses a correctly trusted connection.
    exercise('success', 'Do you agree', columns)
for case, expected in (
    ('timeout', 'timed out'),
    ('http-error', 'HTTP error'),
    ('invalid-json', 'invalid terms-of-service'),
    ('invalid-meta', 'invalid terms-of-service'),
):
    mode(case)
    exercise(case, expected)
exercise('connection-refused', 'Check DNS', refused=True)
print('Installed entrypoint failure/retry/success paths: PASS')
