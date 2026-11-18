"""Exercise the backup management journey without changing a real system."""
import subprocess
import unittest
from unittest.mock import Mock, patch

import confconsole


class BackupMenuTests(unittest.TestCase):
    def setUp(self):
        self.ui = confconsole.TurnkeyConsole.__new__(confconsole.TurnkeyConsole)
        self.ui.console = Mock()

    @patch('confconsole.conf.Conf')
    def test_advanced_menu_places_backup_after_networking(self, conf):
        conf.return_value.networking = True
        self.ui.installer = Mock(available=False)
        self.ui.pluginManager = Mock(path_map={})
        items, _ = self.ui._get_advmenu()
        self.assertEqual([item[0] for item in items[:2]], ['Networking', 'Backup'])

    @patch('confconsole.subprocess.run')
    @patch('confconsole.hub_link_status', side_effect=['hub.turnkeylinux.org: NOT CONNECTED',
                                                       'hub.turnkeylinux.org: CONNECTED'])
    def test_disconnected_server_starts_shared_hub_connection(self, _status, run):
        self.assertTrue(self.ui._backup_connect())
        run.assert_called_once_with(['/usr/lib/inithooks/bin/hubservices.py', '--relink'], check=True)

    @patch('confconsole.os.path.isdir', return_value=False)
    def test_menu_shows_status_and_setup_without_rollback(self, _isdir):
        self.ui._backup_connect = Mock(return_value=True)
        self.ui._backup_status = Mock(return_value=(11, 'Backups: Ready to set up'))
        self.ui.console.menu.return_value = ('cancel', '')
        self.assertEqual(self.ui._adv_backup(), 'advanced')
        title, text, choices = self.ui.console.menu.call_args.args
        self.assertEqual(title, 'Backups')
        self.assertIn('Ready to set up', text)
        self.assertNotIn('rollback', text.lower())
        self.assertEqual([name for name, _ in choices], ['Setup', 'Restore'])

    @patch('confconsole.os.path.isdir', return_value=True)
    def test_menu_offers_rollback_only_as_an_available_action(self, _isdir):
        self.ui._backup_connect = Mock(return_value=True)
        self.ui._backup_status = Mock(return_value=(0, 'Backups: Backup ID #1'))
        self.ui.console.menu.return_value = ('cancel', '')
        self.assertEqual(self.ui._adv_backup(), 'advanced')
        _, text, choices = self.ui.console.menu.call_args.args
        self.assertNotIn('rollback', text.lower())
        self.assertIn('Rollback', [name for name, _ in choices])

    @patch('confconsole.subprocess.run')
    def test_passphrase_is_confirmed_and_sent_over_stdin(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, '', '')
        self.ui.console.passwordbox.side_effect = [('ok', 'private phrase'), ('ok', 'private phrase')]
        self.ui._backup_passphrase()
        run.assert_called_once_with(['tklbam-passphrase'], input='private phrase\n', capture_output=True, text=True)

    @patch('confconsole.subprocess.run')
    def test_mismatched_passphrase_does_not_change_key(self, run):
        self.ui.console.passwordbox.side_effect = [('ok', 'one'), ('ok', 'two')]
        self.ui._backup_passphrase()
        run.assert_not_called()

    def test_restore_lists_completed_records_and_sends_password_to_selected_id(self):
        self.ui.backup_progress = Mock(return_value=subprocess.CompletedProcess(
            [], 0, '1\tYes\t2026-11-18 12:00:00\t123\tLAMP\n2\tNo\tNone\t0\tEmpty\n', ''))
        self.ui.console.menu.return_value = ('ok', '1')
        self.ui.console.yesno.return_value = 'ok'
        self.ui.console.passwordbox.return_value = ('ok', 'private phrase')
        self.ui._backup_operation = Mock()
        self.ui._backup_restore()
        self.assertEqual(self.ui.console.menu.call_args.args[2], [('1', 'LAMP  (2026-11-18)')])
        self.ui._backup_operation.assert_called_once_with(
            ['tklbam-restore', '--noninteractive', '1'], 'Restore backup', 'private phrase')

    def test_cancel_restore_never_runs_command(self):
        self.ui.backup_progress = Mock(return_value=subprocess.CompletedProcess([], 0, '1\tNo\tNone\t123\tLAMP\n', ''))
        self.ui.console.menu.return_value = ('ok', '1')
        self.ui.console.yesno.return_value = 'cancel'
        self.ui._backup_operation = Mock()
        self.ui._backup_restore()
        self.ui._backup_operation.assert_not_called()

    @patch('confconsole.os.path.isdir', return_value=True)
    def test_rollback_requires_confirmation(self, _isdir):
        self.ui.console.yesno.return_value = 'ok'
        self.ui._backup_operation = Mock()
        self.ui._backup_rollback()
        self.ui._backup_operation.assert_called_once_with(['tklbam-restore-rollback', '--force'], 'Rollback restore')


if __name__ == '__main__':
    unittest.main()
