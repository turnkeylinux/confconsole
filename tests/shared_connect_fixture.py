#!/usr/bin/python3
"""Run the actual shared UI with fixture exchanges and isolated local state."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile

root = Path(os.environ['INITHOOKS_SOURCE'])
sys.path.insert(0, str(root))
spec = importlib.util.spec_from_file_location('hubservices', root / 'bin/hubservices.py')
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)
state = tempfile.TemporaryDirectory()
ui.onboarding.STATE_DIR = Path(state.name)
ui.hub_push.Notifications.open = lambda code: None
mode = os.environ.get('CONNECT_FIXTURE_MODE', 'ready')
polls = 0


def exchange(*arguments):
    global polls
    if arguments == ('connect', '--start'):
        return {'verification_uri': 'https://hub.turnkeylinux.org/link', 'user_code': 'D34C-F5A9'}
    polls += 1
    if mode == 'pending' and polls == 1:
        return {'status': 'pending'}
    if mode in ('denied', 'expired'):
        return {'status': mode}
    if mode == 'error':
        return {'status': 'error', 'message': 'The Hub is temporarily unavailable. Try again shortly.'}
    return {'connection_status': 'linked'}


ui.mail_call = exchange
ui.main()
