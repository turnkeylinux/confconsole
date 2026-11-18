"""Backup setup navigation and recovery."""
import subprocess
import io
import unittest
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
    @patch('confconsole.subprocess.run')
    def test_success_can_start_first_backup_directly(self, run, _status):
        self.ui.backup_progress = Mock(return_value=subprocess.CompletedProcess([], 0, '', ''))
        run.return_value = subprocess.CompletedProcess([], 0)
        self.ui.console.yesno.return_value = 'ok'
        self.assertEqual(self.ui.backup_setup(), 'usage')
        self.ui.backup_progress.assert_called_once()
        run.assert_called_once_with(['tklbam-backup'], check=False)
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

    def test_cancel_first_backup_does_not_start_it(self):
        self.ui.console.yesno.return_value = 'cancel'
        with patch('confconsole.subprocess.run') as run:
            self.ui.backup_create()
        run.assert_not_called()
        self.ui.console.clear_screen.assert_not_called()

    @patch('confconsole.subprocess.run')
    def test_failed_backup_reports_failure(self, run):
        self.ui.console.yesno.return_value = 'ok'
        run.return_value = subprocess.CompletedProcess([], 1)
        self.ui.backup_create()
        self.assertEqual(self.ui.console.msgbox.call_args.args[0], 'Backup could not finish')

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


class MainScreenTests(unittest.TestCase):
    def run_screen(self, choice, advanced_enabled=True):
        ui = confconsole.TurnkeyConsole.__new__(confconsole.TurnkeyConsole)
        ui.advanced_enabled = advanced_enabled
        ui.console = Mock()
        ui.console.actionbox.return_value = choice
        ui._get_filtered_ifnames = Mock(return_value=['eth0'])
        ui._get_default_nic = Mock(return_value='eth0')
        ui._get_public_ipaddr = Mock(return_value='192.0.2.1')
        ui.appname = 'Test'
        commands = [subprocess.CompletedProcess([], 0, '/usr/bin/tklbam-status\n', ''),
                    subprocess.CompletedProcess([], 11, 'TKLBAM: NOT INITIALIZED\n', '')]
        with patch('confconsole.subprocess.run', side_effect=commands), \
             patch('confconsole.hub_link_status', return_value='hub.turnkeylinux.org: CONNECTED'), \
             patch.object(confconsole.ifutil, 'get_ipv6conf', return_value=(None, None)), \
             patch.object(confconsole.netinfo, 'get_hostname', return_value='test'):
            result = ui.usage()
        return ui, result

    def test_uninitialized_backups_offer_setup_first(self):
        ui, result = self.run_screen('ok')
        self.assertEqual(result, 'backup_setup')
        self.assertIn('Backups: Ready to set up', ui.console.actionbox.call_args.args[1])
        self.assertEqual(ui.console.actionbox.call_args.args[2:], ('Set up backups', 'Advanced Menu'))

    def test_secondary_action_opens_advanced_menu(self):
        _, result = self.run_screen('cancel')
        self.assertEqual(result, 'advanced')

    def test_usage_only_secondary_action_quits(self):
        ui, result = self.run_screen('cancel', advanced_enabled=False)
        self.assertEqual(result, 'quit')
        self.assertEqual(ui.console.actionbox.call_args.args[2:], ('Set up backups', 'Quit'))


if __name__ == '__main__':
    unittest.main()
