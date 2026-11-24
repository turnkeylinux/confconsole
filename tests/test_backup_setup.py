"""Backup setup navigation and recovery."""
import subprocess
import io
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import confconsole


class BackupSetupTests(unittest.TestCase):
    def setUp(self):
        self.ui = confconsole.TurnkeyConsole.__new__(confconsole.TurnkeyConsole)
        self.ui.console = Mock()

    @patch('confconsole.hub_link_status', return_value='hub.turnkeylinux.org: CONNECTED')
    def test_aws_setup_can_be_completed_and_retried(self, _status):
        self.ui.backup_progress = Mock(side_effect=[subprocess.CompletedProcess([], 1, '', 'Finish backup setup and connect your AWS account in the Hub:\n\n  https://hub.turnkeylinux.org/backup/new\n\nThen retry your command.'), subprocess.CompletedProcess([], 0, '', '')])
        self.ui.console.yesno.side_effect = ['ok', 'cancel']
        self.assertEqual(self.ui.backup_setup(), 'usage')
        self.assertEqual(self.ui.backup_progress.call_count, 2)
        self.assertIn('https://hub.turnkeylinux.org/backup/new', self.ui.console.yesno.call_args_list[0].args[0])
        self.assertEqual(self.ui.console.yesno.call_args.kwargs['title'], 'Backups ready')

    @patch('confconsole.hub_link_status', return_value='hub.turnkeylinux.org: CONNECTED')
    def test_success_can_start_first_backup_directly(self, _status):
        self.ui.backup_progress = Mock(return_value=subprocess.CompletedProcess([], 0, '', ''))
        self.ui.run_backup = Mock(return_value=(0, 'Backup succeeded'))
        self.ui.console.yesno.return_value = 'ok'
        self.assertEqual(self.ui.backup_setup(), 'usage')
        self.ui.backup_progress.assert_called_once()
        self.ui.run_backup.assert_called_once_with()
        self.assertEqual(self.ui.console.yesno.call_count, 1)
        self.ui.console.clear_screen.assert_called_once_with()
        self.assertEqual(self.ui.console.msgbox.call_args.args[0], 'Backup complete')

    @patch('confconsole.hub_link_status', return_value='hub.turnkeylinux.org: CONNECTED')
    def test_disabled_backup_points_to_server_access_and_cancel_stops(self, _status):
        self.ui.backup_progress = Mock(return_value=subprocess.CompletedProcess([], 1, '', 'Enable backups for this server in the Hub'))
        self.ui.console.yesno.return_value = 'cancel'
        self.ui.backup_setup()
        self.assertEqual(self.ui.backup_progress.call_count, 1)
        self.assertIn('https://hub.turnkeylinux.org/email/', self.ui.console.yesno.call_args.args[0])

    @patch('confconsole.hub_link_status', return_value='hub.turnkeylinux.org: STATUS UNAVAILABLE')
    @patch('confconsole.subprocess.run')
    def test_unknown_hub_state_does_not_relink(self, run, _status):
        self.ui.backup_setup()
        run.assert_not_called()

    @patch('confconsole.hub_link_status', return_value='hub.turnkeylinux.org: CONNECTED')
    def test_not_now_after_setup_does_not_start_backup(self, _status):
        self.ui.backup_progress = Mock(return_value=subprocess.CompletedProcess([], 0, '', ''))
        self.ui.run_backup = Mock()
        self.ui.console.yesno.return_value = 'cancel'
        self.assertEqual(self.ui.backup_setup(), 'usage')
        self.ui.run_backup.assert_not_called()
        self.ui.console.clear_screen.assert_not_called()

    def test_failed_backup_offers_output_in_console(self):
        self.ui.run_backup = Mock(return_value=(1, 'error: sample failure'))
        self.ui.console.yesno.return_value = 'ok'
        self.ui.backup_create()
        self.ui.run_backup.assert_called_once_with()
        self.assertEqual(self.ui.console.yesno.call_args.kwargs['ok_label'], 'View output')
        self.ui.console.scrollbox.assert_called_once_with('Backup output (use arrows to scroll)', 'error: sample failure')

    def test_plan_limit_explains_hub_recovery_and_allows_back(self):
        self.ui.run_backup = Mock(return_value=(12, 'Plan limit details'))
        self.ui.console.yesno.return_value = 'cancel'
        self.ui.backup_create()
        text = self.ui.console.yesno.call_args.args[0]
        self.assertIn("one backup is already in use", text)
        self.assertIn('https://hub.turnkeylinux.org/billing/', text)
        self.assertEqual(self.ui.console.yesno.call_args.kwargs['ok_label'], 'Retry backup')
        self.assertEqual(self.ui.console.yesno.call_args.kwargs['cancel_label'], 'Back')
        self.assertNotIn('extra_label', self.ui.console.yesno.call_args.kwargs)
        self.ui.console.scrollbox.assert_not_called()

    def test_plan_limit_retry_can_complete_backup(self):
        self.ui.run_backup = Mock(side_effect=[(12, 'Plan limit details'), (0, 'Success')])
        self.ui.console.yesno.return_value = 'ok'
        self.assertEqual(self.ui.backup_create(), 'usage')
        self.assertEqual(self.ui.run_backup.call_count, 2)
        self.assertEqual(self.ui.console.msgbox.call_args.args[0], 'Backup complete')

    def test_unstructured_text_does_not_claim_a_plan_limit(self):
        self.ui.run_backup = Mock(return_value=(1, 'Backup plan record limit reached'))
        self.ui.console.yesno.return_value = 'cancel'
        self.assertEqual(self.ui.backup_create(), 'usage')
        self.assertEqual(self.ui.console.yesno.call_args.kwargs['title'], 'Backup could not finish')

    def test_failure_without_output_is_explained(self):
        self.ui.run_backup = Mock(return_value=(1, ''))
        self.ui.backup_create()
        self.assertIn('No output was available', self.ui.console.msgbox.call_args.args[1])

    @patch('confconsole.subprocess.Popen')
    def test_progress_updates_while_command_runs(self, popen):
        process = popen.return_value.__enter__.return_value
        process.returncode = 0
        process.communicate.side_effect = [subprocess.TimeoutExpired('tklbam-init', 1), ('', '')]
        result = self.ui.backup_progress(['tklbam-init'], 'Setting up backups', 'Preparing the backup profile.')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.ui.console.progress.call_count, 2)
        self.assertNotEqual(self.ui.console.progress.call_args_list[0], self.ui.console.progress.call_args_list[1])

    @patch('confconsole.subprocess.Popen')
    def test_interrupt_stops_the_running_command(self, popen):
        process = popen.return_value.__enter__.return_value
        process.communicate.side_effect = [KeyboardInterrupt, ('', '')]
        with self.assertRaises(KeyboardInterrupt):
            self.ui.backup_progress(['tklbam-init'], 'Setting up backups', 'Preparing.')
        process.terminate.assert_called_once_with()

    def test_clear_screen_resets_the_terminal(self):
        output = io.StringIO()
        with patch('confconsole.sys.stdout', output), patch.object(output, 'isatty', return_value=True):
            confconsole.Console.__new__(confconsole.Console).clear_screen()
        self.assertEqual(output.getvalue(), '\x1b[2J\x1b[H')

    def test_backup_output_is_live_and_available_for_review(self):
        with tempfile.TemporaryDirectory() as directory:
            command = Path(directory) / 'tklbam-backup'
            command.write_text('#!/bin/sh\n[ -t 1 ] || exit 90\nprintf "working\\n"\nprintf "error: sample failure\\n" >&2\nexit 42\n')
            command.chmod(0o755)
            output = types.SimpleNamespace(buffer=io.BytesIO())
            with patch.dict(os.environ, {'PATH': directory + os.pathsep + os.environ.get('PATH', '')}), \
                 patch('confconsole.sys.stdout', output):
                status, recorded = self.ui.run_backup()
            self.assertEqual(status, 42)
            self.assertIn('working', output.buffer.getvalue().decode())
            self.assertIn('error: sample failure', output.buffer.getvalue().decode())
            self.assertIn('error: sample failure', recorded)

    @patch('confconsole.os.read', side_effect=KeyboardInterrupt)
    @patch('confconsole.subprocess.Popen')
    def test_interrupt_stops_the_backup(self, popen, _read):
        process = popen.return_value
        process.poll.return_value = None
        with self.assertRaises(KeyboardInterrupt):
            self.ui.run_backup()
        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=5)


class MainScreenTests(unittest.TestCase):
    def setUp(self):
        status = patch('confconsole.security_updates_status', return_value='Checked today')
        status.start()
        self.addCleanup(status.stop)

    def run_screen(self, choice, advanced_enabled=True, backup_state=11):
        ui = confconsole.TurnkeyConsole.__new__(confconsole.TurnkeyConsole)
        ui.advanced_enabled = advanced_enabled
        ui.console = Mock()
        ui.console.actionbox.return_value = choice
        ui._get_filtered_ifnames = Mock(return_value=['eth0'])
        ui._get_default_nic = Mock(return_value='eth0')
        ui._get_public_ipaddr = Mock(return_value='192.0.2.1')
        ui.appname = 'Test'
        commands = [subprocess.CompletedProcess([], 0, '/usr/bin/tklbam-status\n', ''),
                    subprocess.CompletedProcess([], backup_state, 'TKLBAM status\n', '')]
        with patch('confconsole.subprocess.run', side_effect=commands), \
             patch('confconsole.local_hub_status', return_value={'connection_status': 'linked'}), \
             patch('confconsole.notification_recipient', return_value='Security contact: admin@example.net'), \
             patch.object(confconsole.ifutil, 'get_ipv6conf', return_value=(None, None)), \
             patch.object(confconsole.netinfo, 'get_hostname', return_value='test'):
            result = ui.usage()
        return ui, result

    def test_admin_email_precedes_service_and_backup_information(self):
        ui, _ = self.run_screen('ok')
        text = ui.console.actionbox.call_args.args[1]
        self.assertIn('Security contact:  admin@example.net\nEmail delivery:', text)
        self.assertLess(text.index('Security contact:'), text.index('Backups:'))
        self.assertTrue(text.endswith('  Backups:         Ready to set up\n\n'
                                      'Security updates:  Checked today'))

    def test_uninitialized_backups_offer_setup_first(self):
        ui, result = self.run_screen('ok')
        self.assertEqual(result, 'backup_setup')
        self.assertIn('Backups:         Ready to set up', ui.console.actionbox.call_args.args[1])
        self.assertEqual(ui.console.actionbox.call_args.args[2:], ('Set up backups', 'Advanced Menu'))

    def test_secondary_action_opens_advanced_menu(self):
        for backup_state in (10, 11):
            with self.subTest(backup_state=backup_state):
                _, result = self.run_screen('cancel', backup_state=backup_state)
                self.assertEqual(result, 'advanced')

    def test_first_backup_action_is_first(self):
        ui, result = self.run_screen('ok', backup_state=10)
        self.assertEqual(result, 'backup_create')
        self.assertIn('Backups:         Ready for first backup', ui.console.actionbox.call_args.args[1])
        self.assertEqual(ui.console.actionbox.call_args.args[2:], ('Create backup', 'Advanced Menu'))

    def test_failed_update_offers_install_before_advanced_on_standard_screen(self):
        terminal = os.terminal_size((80, 24))
        with patch('confconsole.security_updates_status', return_value='Daily update failed'), \
             patch('confconsole.get_terminal_size', return_value=terminal):
            ui, result = self.run_screen('ok')
        self.assertEqual(result, 'install_security_updates')
        self.assertEqual(ui.console.actionbox.call_args.args[2:],
                         ('Install security updates', 'Advanced Menu'))
        self.assertIn('Security updates:  Daily update failed', ui.console.actionbox.call_args.args[1])

    def test_failed_update_buttons_fit_on_narrow_screen(self):
        terminal = os.terminal_size((50, 24))
        with patch('confconsole.security_updates_status', return_value='Daily update failed'), \
             patch('confconsole.get_terminal_size', return_value=terminal):
            ui, result = self.run_screen('ok')
        self.assertEqual(result, 'install_security_updates')
        self.assertEqual(ui.console.actionbox.call_args.args[2:], ('Install updates', 'Advanced Menu'))

    def test_failed_update_keeps_all_three_actions_on_wide_screen(self):
        terminal = os.terminal_size((100, 30))
        with patch('confconsole.security_updates_status', return_value='Daily update failed'), \
             patch('confconsole.get_terminal_size', return_value=terminal):
            ui, result = self.run_screen('extra')
        self.assertEqual(result, 'install_security_updates')
        self.assertEqual(ui.console.actionbox.call_args.args[2:], ('Set up backups', 'Advanced Menu'))
        self.assertEqual(ui.console.actionbox.call_args.kwargs['extra_label'], 'Install security updates')

    def test_install_runs_shared_terminal_flow_and_returns_to_usage(self):
        ui = confconsole.TurnkeyConsole.__new__(confconsole.TurnkeyConsole)
        with patch('confconsole.run_security_updates') as run:
            self.assertEqual(ui.install_security_updates(), 'usage')
        run.assert_called_once_with()

    def test_usage_only_secondary_action_quits(self):
        ui, result = self.run_screen('cancel', advanced_enabled=False)
        self.assertEqual(result, 'quit')
        self.assertEqual(ui.console.actionbox.call_args.args[2:], ('Set up backups', 'Quit'))


class BackupSummaryTests(unittest.TestCase):
    def test_current_run_statistics_are_shown_while_output_stays_live(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'backup.log'
            log.write_text('---[ Backup Statistics ]---\nNewFiles 999\n---\n')
            def run():
                with log.open('a') as stream:
                    stream.write('---[ Backup Statistics ]---\nElapsedTime 8.00 (8 seconds)\n'
                                 'NewFiles 3\nChangedFiles 2\nDeletedFiles 1\n'
                                 'TotalDestinationSizeChange 1024 (1 KB)\nErrors 0\n---\n')
                return 0, 'Backup succeeded'
            ui = confconsole.TurnkeyConsole.__new__(confconsole.TurnkeyConsole)
            ui.console = Mock()
            with patch.object(confconsole, 'BACKUP_LOG', str(log)), patch.object(ui, 'run_backup', side_effect=run) as command:
                self.assertEqual(ui.backup_create(), 'usage')
            command.assert_called_once_with()
            message = ui.console.msgbox.call_args.args[1]
            self.assertIn('Duration: 8 seconds', message)
            self.assertIn('Data uploaded: 1 KB', message)
            self.assertIn('New files: 3', message)
            self.assertNotIn('999', message)

    def test_missing_or_replaced_log_does_not_show_old_statistics(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'backup.log'
            log.write_text('---[ Backup Statistics ]---\nNewFiles 999\n---\n')
            with patch.object(confconsole, 'BACKUP_LOG', str(log)):
                position = confconsole.backup_log_position()
                self.assertEqual(confconsole.backup_summary(position), '')
                log.rename(log.with_suffix('.old'))
                log.write_text('---[ Backup Statistics ]---\nNewFiles 1\n---\n')
                self.assertEqual(confconsole.backup_summary(position), '')


if __name__ == '__main__':
    unittest.main()
