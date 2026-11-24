"""Daily security update status on the service screen."""
from datetime import datetime, timedelta, timezone
import json
import subprocess
import unittest
from unittest.mock import patch

import confconsole


class SecurityUpdateStatusTests(unittest.TestCase):
    def setUp(self):
        self.today = datetime.now(timezone.utc).isoformat()

    def show(self, daily, **fields):
        fields.update(schema_version=1, daily=daily)
        result = subprocess.CompletedProcess([], 0, json.dumps(fields), '')
        with patch('confconsole.os.path.isfile', return_value=True), \
             patch('confconsole.subprocess.run', return_value=result):
            return confconsole.security_updates_status()

    def test_success_and_reboot(self):
        daily = dict(result='success', last_attempt=self.today, last_success=self.today)
        self.assertTrue(self.show(daily).startswith('Successful today '))
        self.assertTrue(self.show(daily, reboot_required=True).endswith(', reboot needed'))

    def test_overdue_only_after_48_hours(self):
        fixed_now = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
        with patch('confconsole.datetime') as clock:
            clock.now.return_value = fixed_now
            clock.fromisoformat.side_effect = datetime.fromisoformat
            for age, expected in ((timedelta(hours=48), 'Successful'),
                                  (timedelta(hours=48, seconds=1), 'Overdue; last successful')):
                stamp = (fixed_now - age).isoformat()
                daily = dict(result='success', last_attempt=stamp, last_success=stamp)
                self.assertTrue(self.show(daily).startswith(expected))

    def test_daily_result_wins_over_manual(self):
        daily = dict(result='failed', last_attempt=self.today, last_success=None)
        self.assertEqual(self.show(daily, result='success'), 'Daily update failed')
        daily['result'] = 'interrupted'
        self.assertEqual(self.show(daily), 'Daily update failed')
        daily['result'] = 'running'
        self.assertEqual(self.show(daily), 'Daily update running')

    def test_invalid_or_missing_daily_is_unknown(self):
        for daily in (None, {}, {'result': 'unknown'}, {'result': 'future'}):
            self.assertEqual(self.show(daily), 'Status unavailable')
        for stamp in ('invalid', (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                      '2023-01-02T12:00:00'):
            self.assertEqual(self.show(dict(result='success', last_attempt=stamp, last_success=stamp)),
                             'Status unavailable')
        with patch('confconsole.os.path.isfile', return_value=False):
            self.assertEqual(confconsole.security_updates_status(), 'Status unavailable')
        with patch('confconsole.os.path.isfile', return_value=True), \
             patch('confconsole.subprocess.run', side_effect=subprocess.TimeoutExpired('helper', 3)):
            self.assertEqual(confconsole.security_updates_status(), 'Status unavailable')

    def test_security_updates_are_separate_and_last(self):
        text = confconsole.hub_service_lines(
            {'connection_status': 'disconnected'}, 'Backups: Ready to set up',
            security_updates='Successful today 19:22')
        self.assertTrue(text.endswith('  Backups:         Ready to set up\n\n'
                                      'Security updates:  Successful today 19:22'))
