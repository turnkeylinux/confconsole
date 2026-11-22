"""Exercise the backup management journey without changing a real system."""
import subprocess
import os
import signal
import sys
import types
import unittest
from unittest.mock import Mock, patch

import confconsole


class BackupMenuTests(unittest.TestCase):
    def setUp(self):
        self.ui = confconsole.TurnkeyConsole.__new__(confconsole.TurnkeyConsole)
        self.ui.console = Mock()

    def test_padding_row_is_not_an_action(self):
        console = confconsole.Console.__new__(confconsole.Console)
        console.width, console.height = 65, 22
        console._wrapper = Mock(side_effect=[('ok', ''), ('ok', 'Backup')])
        with patch('confconsole.get_terminal_size', return_value=confconsole.os.terminal_size((80, 24))):
            code, choice = console.menu('Backups', 'Status', [('Backup', 'Create a backup')], compact=True, pad=True)
        self.assertEqual((code, choice), ('ok', 'Backup'))
        self.assertEqual(console._wrapper.call_count, 2)
        self.assertEqual(console._wrapper.call_args.kwargs['default_item'], 'Backup')

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
        self.assertEqual([name for name, _ in choices], ['Setup', 'Email reports', 'Restore'])

    def test_success_email_preference_can_be_enabled_and_disabled(self):
        import tempfile
        from pathlib import Path
        self.ui._backup_connect = Mock(return_value=True)
        self.ui._backup_status = Mock(return_value=(0, 'Ready'))
        self.ui.console.yesno.return_value = 'ok'
        with tempfile.TemporaryDirectory() as directory:
            flag = str(Path(directory) / 'email-success')
            with patch('confconsole.BACKUP_EMAIL_SUCCESS', flag):
                self.ui.console.menu.side_effect = [('ok', 'Email reports'), ('cancel', '')]
                self.ui._adv_backup()
                self.assertTrue(os.path.exists(flag))
                self.ui.console.menu.side_effect = [('ok', 'Email reports'), ('cancel', '')]
                self.ui._adv_backup()
                self.assertFalse(os.path.exists(flag))

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

    def test_password_fields_display_asterisks(self):
        console = confconsole.Console.__new__(confconsole.Console)
        console._wrapper = Mock(return_value=('ok', 'secret'))
        self.assertEqual(console.passwordbox('Title', 'Enter:'), ('ok', 'secret'))
        self.assertTrue(console._wrapper.call_args.kwargs['insecure'])

    @patch('confconsole.subprocess.run')
    def test_blank_generates_displays_and_saves_passphrase(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, '', '')
        self.ui.console.passwordbox.return_value = ('ok', '')
        self.ui.console.show_generated_passphrase.return_value = True
        module = types.ModuleType('libinithooks')
        module.passwords = Mock(generate=Mock(return_value='generated-secret'))
        with patch.dict(sys.modules, {'libinithooks': module}):
            self.ui._backup_passphrase()
        self.ui.console.passwordbox.assert_called_once()
        self.ui.console.show_generated_passphrase.assert_called_once_with('generated-secret')
        run.assert_called_once_with(['tklbam-passphrase'], input='generated-secret\n', capture_output=True, text=True)

    @patch('confconsole.subprocess.run')
    def test_cancelling_generated_passphrase_does_not_change_key(self, run):
        self.ui.console.passwordbox.return_value = ('ok', '')
        self.ui.console.show_generated_passphrase.return_value = False
        module = types.ModuleType('libinithooks')
        module.passwords = Mock(generate=Mock(return_value='generated-secret'))
        with patch.dict(sys.modules, {'libinithooks': module}):
            self.ui._backup_passphrase()
        run.assert_not_called()

    @patch('confconsole.subprocess.run')
    def test_generation_falls_back_when_inithooks_generator_is_unavailable(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, '', '')
        self.ui.console.passwordbox.return_value = ('ok', '')
        self.ui.console.show_generated_passphrase.return_value = True
        module = types.ModuleType('libinithooks')
        with patch.dict(sys.modules, {'libinithooks': module}), \
             patch('confconsole.secrets.token_urlsafe', return_value='fallback-secret'):
            self.ui._backup_passphrase()
        self.ui.console.show_generated_passphrase.assert_called_once_with('fallback-secret')
        run.assert_called_once_with(['tklbam-passphrase'], input='fallback-secret\n', capture_output=True, text=True)

    def test_generated_passphrase_is_passed_to_dialog_through_pipe(self):
        console = confconsole.Console.__new__(confconsole.Console)
        console.title = 'Test'
        secret = 'Generated-credential-123'
        payloads = []
        def run(args, **kwargs):
            self.assertNotIn(secret, ' '.join(args))
            self.assertNotIn(secret, str(kwargs.get('env', {})))
            payloads.append(os.read(kwargs['pass_fds'][0], 4096).decode())
            return subprocess.CompletedProcess(args, 0)
        with patch('confconsole.conf.Conf') as conf, patch('confconsole.subprocess.run', side_effect=run):
            conf.return_value.copy_paste = False
            self.assertTrue(console.show_generated_passphrase(secret))
        self.assertIn(secret, payloads[0])

    def test_restore_lists_completed_records_and_sends_password_to_selected_id(self):
        self.ui.backup_progress = Mock(return_value=subprocess.CompletedProcess(
            [], 0, '1\tYes\t2026-11-17 12:00:00\t2026-11-18 12:00:00\t123\tLAMP\n2\tNo\tNone\tNone\t0\tEmpty\n', ''))
        self.ui.console.menu.return_value = ('ok', '1')
        self.ui.console.yesno.return_value = 'ok'
        self.ui.console.passwordbox.return_value = ('ok', 'private phrase')
        self.ui._backup_operation = Mock()
        self.ui._backup_restore()
        choices = self.ui.console.menu.call_args.args[2]
        self.assertEqual(len(choices), 1)
        self.assertEqual(choices[0][0], '1')
        for detail in ('Yes', '2026-11-17', '2026-11-18', '0.01', 'LAMP'):
            self.assertIn(detail, choices[0][1])
        self.ui._backup_operation.assert_called_once_with(
            ['tklbam-restore', '--noninteractive', '1'], 'Restore backup', 'private phrase')

    def test_cancel_restore_never_runs_command(self):
        self.ui.backup_progress = Mock(return_value=subprocess.CompletedProcess([], 0, '1\tNo\tNone\tNone\t123\tLAMP\n', ''))
        self.ui.console.menu.return_value = ('ok', '1')
        self.ui.console.yesno.return_value = 'cancel'
        self.ui._backup_operation = Mock()
        self.ui._backup_restore()
        self.ui._backup_operation.assert_not_called()

    def test_long_label_is_preserved_in_restore_confirmation(self):
        label = 'A very long backup label that exceeds the visible menu width'
        self.ui.backup_progress = Mock(return_value=subprocess.CompletedProcess(
            [], 0, '42\tNo\t2026-11-17\t2026-11-18\t795143\t' + label + '\n', ''))
        self.ui.console.menu.return_value = ('ok', '42')
        self.ui.console.yesno.return_value = 'cancel'
        with patch('confconsole.get_terminal_size', return_value=confconsole.os.terminal_size((60, 24))):
            self.ui._backup_restore()
        self.assertIn('…', self.ui.console.menu.call_args.args[2][0][1])
        self.assertIn(label, self.ui.console.yesno.call_args.args[0])

    def test_restore_picker_shows_all_record_fields_and_uses_terminal_width(self):
        self.ui.backup_progress = Mock(return_value=subprocess.CompletedProcess(
            [], 0, '7\tNo\t2026-11-17 10:00:00\t2026-11-18 12:00:00\t795143\tLAMP\n', ''))
        self.ui.console.width, self.ui.console.height = 65, 25
        widths = []
        self.ui.console.menu.side_effect = lambda *args, **kwargs: (widths.append(self.ui.console.width) or ('cancel', ''))
        with patch('confconsole.get_terminal_size', return_value=confconsole.os.terminal_size((100, 30))):
            self.ui._backup_restore()
        _, text, choices = self.ui.console.menu.call_args.args
        self.assertIn('Created', text)
        self.assertIn('Updated', text)
        self.assertIn('Size MB', text)
        for value in ('7', 'No', '2026-11-17', '2026-11-18', '0.76', 'LAMP'):
            self.assertIn(value, choices[0][1])
        self.assertEqual(widths, [96])
        self.assertEqual(self.ui.console.width, 65)
        self.assertTrue(self.ui.console.menu.call_args.kwargs['no_tags'])

    def test_resize_rebuilds_picker_without_reloading_records(self):
        self.ui.backup_progress = Mock(return_value=subprocess.CompletedProcess(
            [], 0, '7\tNo\t2026-11-17\t2026-11-18\t795143\tLAMP\n', ''))
        self.ui.console.width, self.ui.console.height = 65, 25
        original_handler = signal.getsignal(signal.SIGWINCH)
        def menu(*args, **kwargs):
            if self.ui.console.menu.call_count == 1:
                os.kill(os.getpid(), signal.SIGWINCH)
                raise confconsole.dialog.DialogTerminatedBySignal('resized')
            return ('cancel', '')
        self.ui.console.menu.side_effect = menu
        with patch('confconsole.get_terminal_size', side_effect=[
                os.terminal_size((80, 24)), os.terminal_size((120, 24))]):
            self.ui._backup_restore()
        self.assertEqual(self.ui.backup_progress.call_count, 1)
        self.assertEqual(self.ui.console.menu.call_count, 2)
        self.assertIn('Select a backup.', self.ui.console.menu.call_args.args[1])
        self.assertEqual(signal.getsignal(signal.SIGWINCH), original_handler)

    @patch('confconsole.os.path.isdir', return_value=True)
    def test_rollback_requires_confirmation(self, _isdir):
        self.ui.console.yesno.return_value = 'ok'
        self.ui._backup_operation = Mock()
        self.ui._backup_rollback()
        self.ui._backup_operation.assert_called_once_with(['tklbam-restore-rollback', '--force'], 'Rollback restore')


if __name__ == '__main__':
    unittest.main()
