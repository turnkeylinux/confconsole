"""Local security update status shown on the service screen."""
from datetime import datetime, timedelta, timezone
import json
import subprocess
import unittest
from unittest.mock import patch

import confconsole


class SecurityUpdateStatusTests(unittest.TestCase):
    def setUp(self):
        self.today = datetime.now(timezone.utc).isoformat()

    def show(self, **fields):
        result = subprocess.CompletedProcess([], 0, json.dumps(fields), '')
        with patch('confconsole.os.path.isfile', return_value=True), \
             patch('confconsole.subprocess.run', return_value=result) as run:
            text = confconsole.security_updates_status()
        run.assert_called_once_with(['/usr/sbin/turnkey-security-updates-status', '--json'],
                                    capture_output=True, text=True, timeout=3, check=True)
        return text

    def test_completed_check_and_updates(self):
        fields = dict(schema_version=1, result='success', last_attempt=self.today,
                      last_success=self.today, installed=0, reboot_required=None)
        self.assertEqual(self.show(**fields), 'Checked today')
        fields['installed'] = 3
        self.assertEqual(self.show(**fields), 'Checked today, 3 installed')
        fields['installed'] = None
        self.assertEqual(self.show(**fields), 'Checked today')
        fields['last_attempt'] = '2023-01-01T23:59:00Z'
        fields['last_success'] = '2023-01-02T12:00:00Z'
        self.assertEqual(self.show(**fields), 'Checked 2023-01-02')

    def test_failed_attempt_does_not_report_old_installations(self):
        self.assertEqual(self.show(schema_version=1, result='failed',
                                   last_attempt='2023-01-02T12:00:00Z',
                                   last_success='2023-01-01T12:00:00Z', installed=3),
                         'Failed 2023-01-02')

    def test_missing_invalid_and_reboot_status(self):
        with patch('confconsole.os.path.isfile', return_value=False):
            self.assertEqual(confconsole.security_updates_status(), 'Status unavailable')
        with patch('confconsole.os.path.isfile', return_value=True), \
             patch('confconsole.subprocess.run', return_value=subprocess.CompletedProcess([], 0, '{', '')):
            self.assertEqual(confconsole.security_updates_status(), 'Status unavailable')
        self.assertEqual(self.show(schema_version=1, result='unknown'), 'Status unavailable')
        self.assertEqual(self.show(schema_version=True, result='success', last_attempt=self.today,
                                   last_success=self.today, installed=0), 'Status unavailable')
        self.assertEqual(self.show(schema_version=1, result='success',
                                   last_attempt='invalid', last_success=self.today, installed=0),
                         'Status unavailable')
        self.assertEqual(self.show(schema_version=1, result='success', last_attempt=self.today,
                                   last_success=self.today, installed=0, reboot_required=True),
                         'Checked today, reboot needed')

    def test_invalid_timestamp_counts_and_helper_failures(self):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        for stamp in ('invalid', future, '2023-01-02T12:00:00'):
            self.assertEqual(self.show(schema_version=1, result='success', last_attempt=stamp,
                                       last_success=stamp, installed=0), 'Status unavailable')
        for count in (-1, True, '3'):
            self.assertEqual(self.show(schema_version=1, result='success', last_attempt=self.today,
                                       last_success=self.today, installed=count), 'Status unavailable')
        self.assertEqual(self.show(schema_version=1, result='success', last_attempt=self.today,
                                   last_success='2023-01-01T00:00:00Z', installed=0),
                         'Status unavailable')
        with patch('confconsole.os.path.isfile', return_value=True), \
             patch('confconsole.subprocess.run', side_effect=subprocess.TimeoutExpired('helper', 3)):
            self.assertEqual(confconsole.security_updates_status(), 'Status unavailable')

    def test_running_and_interrupted_status(self):
        self.assertEqual(self.show(schema_version=1, result='running', last_attempt=self.today), 'Checking...')
        self.assertEqual(self.show(schema_version=1, result='interrupted', last_attempt=self.today), 'Interrupted today')

    def test_security_updates_are_separate_and_last(self):
        text = confconsole.hub_service_lines(
            {'connection_status': 'disconnected'}, 'Backups: Ready to set up',
            security_updates='Checked today, 3 installed')
        self.assertTrue(text.endswith('  Backups:         Ready to set up\n\n'
                                      'Security updates:  Checked today, 3 installed'))


if __name__ == '__main__':
    unittest.main()
