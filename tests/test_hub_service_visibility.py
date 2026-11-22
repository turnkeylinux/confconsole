"""Hub services are displayed individually from the local status response."""
import subprocess
import unittest
from unittest.mock import Mock, patch
import confconsole

class HubServiceVisibilityTests(unittest.TestCase):
    def test_disconnected_has_all_rows_and_backup_status(self):
        text = confconsole.hub_service_lines({'connection_status': 'disconnected'}, 'Backups: Ready to set up')
        self.assertIn('hub.turnkeylinux.org: Not connected\n\n', text)
        self.assertIn('Email delivery:  Not connected', text)
        self.assertIn('DNS:             Not connected', text)
        self.assertIn('Backups:         Ready to set up', text)

    def test_connected_services_are_independent(self):
        status = {'connection_status': 'linked', 'status': 'ready', 'mode': 'hub',
                  'services': {'mail': {'enabled': True}, 'dns': {'enabled': False}}}
        text = confconsole.hub_service_lines(status, 'TKLBAM: Backup ID #4')
        self.assertIn('Email delivery:  Connected', text)
        self.assertIn('DNS:             Disabled', text)
        self.assertIn('Backups:         Backup ID #4', text)
        status.update(mail_preference='manual')
        self.assertIn('Email delivery:  Not using Hub', confconsole.hub_service_lines(status, ''))

    def test_pending_errors_and_unknown_are_not_claimed_connected(self):
        status = {'connection_status': 'linked', 'status': 'linked', 'setup_pending': True,
                  'services': {'mail': {'enabled': True}, 'dns': {'enabled': True}}}
        text = confconsole.hub_service_lines(status, '')
        self.assertIn('Email delivery:  Setup in progress', text)
        self.assertIn('DNS:             Setup in progress', text)
        status['services']['dns']['error'] = 'failed'
        self.assertIn('DNS:             Needs attention', confconsole.hub_service_lines(status, ''))
        self.assertIn('Status unavailable', confconsole.hub_service_lines({}, ''))

    def test_local_status_errors_are_unknown(self):
        with patch('confconsole.subprocess.run', side_effect=subprocess.TimeoutExpired('status', 5)):
            self.assertEqual(confconsole.local_hub_status(), {})
        with patch('confconsole.subprocess.run', return_value=subprocess.CompletedProcess([], 0, '[]', '')):
            self.assertEqual(confconsole.local_hub_status(), {})

    def test_disconnected_screen_offers_hub_connection(self):
        ui = confconsole.TurnkeyConsole.__new__(confconsole.TurnkeyConsole)
        ui.advanced_enabled = True
        ui.console = Mock()
        ui.console.actionbox.return_value = 'ok'
        ui._get_filtered_ifnames = Mock(return_value=['eth0'])
        ui._get_default_nic = Mock(return_value='eth0')
        ui._get_public_ipaddr = Mock(return_value='192.0.2.1')
        ui.appname = 'Test'
        commands = [subprocess.CompletedProcess([], 0, '/usr/bin/tklbam-status\n', ''),
                    subprocess.CompletedProcess([], 11, 'not initialized\n', '')]
        with patch('confconsole.subprocess.run', side_effect=commands), \
             patch('confconsole.local_hub_status', return_value={'connection_status': 'disconnected'}), \
             patch('confconsole.notification_recipient', return_value='Security contact: Not set'), \
             patch.object(confconsole.ifutil, 'get_ipv6conf', return_value=(None, None)), \
             patch.object(confconsole.netinfo, 'get_hostname', return_value='test'):
            self.assertEqual(ui.usage(), 'connect_hub')
        self.assertEqual(ui.console.actionbox.call_args.args[2], 'Connect to Hub')
        self.assertIn('Email delivery:  Not connected', ui.console.actionbox.call_args.args[1])

    def test_connect_uses_shared_approval_flow_and_returns_to_usage(self):
        ui = confconsole.TurnkeyConsole.__new__(confconsole.TurnkeyConsole)
        ui.console = Mock()
        with patch('confconsole.subprocess.run') as run:
            self.assertEqual(ui.connect_hub(), 'usage')
        run.assert_called_once_with(['/usr/lib/inithooks/bin/hubservices.py', '--relink'], check=True)
        self.assertIn('return here', ui.console.msgbox.call_args.args[1])

    def test_connect_failure_has_recovery_message(self):
        ui = confconsole.TurnkeyConsole.__new__(confconsole.TurnkeyConsole)
        ui.console = Mock()
        with patch('confconsole.subprocess.run', side_effect=OSError('missing')):
            self.assertEqual(ui.connect_hub(), 'usage')
        self.assertIn('Try again', ui.console.msgbox.call_args.args[1])
