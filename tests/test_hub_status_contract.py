"""Verify the console against the real local Inithooks status producer.

Set INITHOOKS_SOURCE to an Inithooks checkout when it is not installed.
"""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import confconsole

source = os.environ.get('INITHOOKS_SOURCE')
helper = Path(source) / 'bin/turnkey-hub' if source else Path('/usr/lib/inithooks/bin/turnkey-hub')

@unittest.skipUnless(helper.is_file(), 'Inithooks helper unavailable; set INITHOOKS_SOURCE')
class InithooksStatusContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        loader = importlib.machinery.SourceFileLoader('real_turnkey_hub_fixture', str(helper))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        cls.helper = importlib.util.module_from_spec(spec)
        loader.exec_module(cls.helper)

    def status_from_disk(self, state):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'state.json').write_text(json.dumps(state))
            with patch.object(self.helper, 'STATE_DIR', path):
                return self.helper.Mail(recover=False).status(refresh=False)

    def test_disconnected_state_is_emitted_by_real_helper(self):
        status = self.status_from_disk({})
        self.assertEqual(status['connection_status'], 'disconnected')
        text = confconsole.hub_service_lines(status, 'Backups: Ready to set up')
        self.assertIn('Email delivery:  Not connected', text)
        self.assertIn('DNS:             Not connected', text)

    def test_email_failure_does_not_hide_enabled_dns(self):
        status = self.status_from_disk({
            'link': {'mode': 'hub', 'control_secret': 'fixture'},
            'provision_pending': True,
            'services': {'mail': {'enabled': True, 'status': 'unavailable'},
                         'dns': {'enabled': True, 'hostname': 'fixture.tklapp.com'}},
        })
        self.assertTrue(status['setup_pending'])
        text = confconsole.hub_service_lines(status, 'Backups: Ready to set up')
        self.assertIn('Email delivery:  Needs attention', text)
        self.assertIn('DNS:             Enabled in Hub', text)

    def test_successful_mail_survives_unrelated_pending_provisioning(self):
        status = self.status_from_disk({
            'link': {'mode': 'hub', 'control_secret': 'fixture'},
            'active': {'mode': 'hub', 'status': 'ready'},
            'provision_pending': True,
            'services': {'mail': {'enabled': True, 'status': 'active'},
                         'dns': {'enabled': False}},
        })
        text = confconsole.hub_service_lines(status, 'Backups: Backup ID #1')
        self.assertIn('Email delivery:  Connected', text)
        self.assertIn('DNS:             Disabled', text)
        self.assertIn('Backups:         Backup ID #1', text)

    def test_read_only_status_avoids_recovery_and_write_lock(self):
        import contextlib
        import io
        import sys
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'state.json').write_text('{}')
            with patch.object(self.helper, 'STATE_DIR', path), \
                 patch.object(self.helper.os, 'geteuid', return_value=0), \
                 patch.object(self.helper.os, 'umask'), \
                 patch.object(self.helper, 'locked', side_effect=AssertionError('write lock used')), \
                 patch.object(self.helper.Mail, 'recover', side_effect=AssertionError('recovery ran')), \
                 patch.object(sys, 'argv', ['turnkey-hub', 'status', '--local', '--read-only', '--json']), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(self.helper.main(), 0)
            self.assertEqual(json.loads(output.getvalue())['connection_status'], 'disconnected')
            self.assertFalse((path / 'lock').exists())

    def test_console_uses_read_only_and_falls_back_only_for_older_helper(self):
        old = subprocess.CompletedProcess([], 2, '', 'error: unrecognized arguments: --read-only')
        ok = subprocess.CompletedProcess([], 0, '{"connection_status":"linked"}', '')
        with patch.object(confconsole.subprocess, 'run', side_effect=[old, ok]) as run:
            self.assertEqual(confconsole.local_hub_status()['connection_status'], 'linked')
        self.assertIn('--read-only', run.call_args_list[0].args[0])
        self.assertNotIn('--read-only', run.call_args_list[1].args[0])
        with patch.object(confconsole.subprocess, 'run', return_value=ok) as run:
            self.assertEqual(confconsole.local_hub_status()['connection_status'], 'linked')
        self.assertEqual(run.call_count, 1)
