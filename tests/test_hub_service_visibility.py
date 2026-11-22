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
        self.assertIn('Email delivery:  Needs attention', confconsole.hub_service_lines(status, ''))

    def test_pending_errors_and_unknown_are_not_claimed_connected(self):
        status = {'connection_status': 'linked', 'status': 'linked', 'setup_pending': True,
                  'services': {'mail': {'enabled': True}, 'dns': {'enabled': True}}}
        text = confconsole.hub_service_lines(status, '')
        self.assertIn('Email delivery:  Setup in progress', text)
        self.assertIn('DNS:             Enabled in Hub', text)
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
        with patch('confconsole.subprocess.run', return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(ui.connect_hub(), 'usage')
        run.assert_called_once_with(['/usr/lib/inithooks/bin/hubservices.py', '--relink'])
        self.assertIn('return here', ui.console.msgbox.call_args.args[1])

    def test_connect_failure_has_recovery_message(self):
        ui = confconsole.TurnkeyConsole.__new__(confconsole.TurnkeyConsole)
        ui.console = Mock()
        with patch('confconsole.subprocess.run', side_effect=OSError('missing')):
            self.assertEqual(ui.connect_hub(), 'usage')
        self.assertIn('Try again', ui.console.msgbox.call_args.args[1])


class HubServiceCombinationTests(unittest.TestCase):
    """Cross product of common service selections reported by the local helper."""

    def test_each_service_choice_is_shown_without_implying_others(self):
        emails = [
            ({'enabled': True, 'status': 'active'}, 'hub', 'ready', 'hub', 'Connected'),
            ({'enabled': False, 'status': 'disabled'}, '', 'linked', 'hub', 'Disabled'),
            ({'enabled': True, 'status': 'active'}, 'custom', 'ready', 'manual', 'Custom SMTP'),
            ({'enabled': True, 'status': 'unavailable'}, '', 'linked', 'hub', 'Needs attention'),
        ]
        dns_states = [({'enabled': True, 'hostname': 'test.tklapp.com'}, 'Enabled in Hub'),
                      ({'enabled': False, 'status': 'disabled'}, 'Disabled'),
                      ({'enabled': False, 'status': 'revoked'}, 'Needs attention')]
        backups = [('Backups: Ready to set up', 'Ready to set up'),
                   ('Backups: Ready for first backup', 'Ready for first backup'),
                   ('TKLBAM: Backup ID #4, Updated Tue 2026-11-17 13:50',
                    'Backup ID #4, Updated Tue 2026-11-17 13:50')]
        for mail, mode, mail_status, preference, expected_mail in emails:
            for dns, expected_dns in dns_states:
                for backup, expected_backup in backups:
                    with self.subTest(mail=expected_mail, dns=expected_dns, backup=expected_backup):
                        state = {'connection_status': 'linked', 'status': mail_status,
                                 'mode': mode, 'mail_preference': preference,
                                 'services': {'mail': mail, 'dns': dns}}
                        text = confconsole.hub_service_lines(state, backup)
                        self.assertIn('hub.turnkeylinux.org: Connected', text)
                        self.assertIn('Email delivery:  ' + expected_mail, text)
                        self.assertIn('DNS:             ' + expected_dns, text)
                        self.assertIn('Backups:         ' + expected_backup, text)

    def test_pending_email_does_not_hide_ready_dns(self):
        # turnkey-hub can initialize DNS independently while email recovery is
        # pending: test_modern_dns_proceeds_when_email_recovery_is_unavailable.
        state = {'connection_status': 'linked', 'status': 'linked', 'setup_pending': True,
                 'services': {'mail': {'enabled': True, 'status': 'unavailable'},
                              'dns': {'enabled': True, 'hostname': 'test.tklapp.com'}}}
        text = confconsole.hub_service_lines(state, 'Backups: Ready to set up')
        self.assertIn('Email delivery:  Needs attention', text)
        self.assertIn('DNS:             Enabled in Hub', text)

    def test_pending_dns_does_not_change_completed_email(self):
        state = {'connection_status': 'linked', 'mode': 'hub', 'status': 'ready',
                 'setup_pending': True,
                 'services': {'mail': {'enabled': True, 'status': 'active'},
                              'dns': {'enabled': False, 'status': 'revoked'}}}
        text = confconsole.hub_service_lines(state, 'TKLBAM: Backup ID #4')
        self.assertIn('Email delivery:  Connected', text)
        self.assertIn('DNS:             Needs attention', text)

    def test_missing_service_does_not_imply_it_is_connected(self):
        for services in ({}, {'mail': {}}, {'dns': {}}, {'mail': None, 'dns': None}):
            with self.subTest(services=services):
                state = {'connection_status': 'linked', 'status': 'linked', 'services': services}
                text = confconsole.hub_service_lines(state, 'Backups: Ready to set up')
                self.assertIn('Email delivery:  Status unavailable', text)
                self.assertIn('DNS:             Status unavailable', text)

    def test_failed_helper_and_invalid_json_are_unknown(self):
        errors = [OSError('missing'), subprocess.TimeoutExpired('status', 5),
                  subprocess.CalledProcessError(1, 'status')]
        for error in errors:
            with self.subTest(error=type(error).__name__), patch('confconsole.subprocess.run', side_effect=error):
                self.assertEqual(confconsole.local_hub_status(), {})
        for output in ('', '{', 'null', '[]', '{"connection_status": "unexpected"}'):
            with self.subTest(output=output), patch('confconsole.subprocess.run',
                    return_value=subprocess.CompletedProcess([], 0, output, '')):
                self.assertEqual(confconsole.local_hub_status(), {})


class HubServiceJourneyTests(unittest.TestCase):
    """Drive the real usage and connect methods through local-helper responses."""

    def make_ui(self):
        ui = confconsole.TurnkeyConsole.__new__(confconsole.TurnkeyConsole)
        ui.advanced_enabled = True
        ui.console = Mock()
        ui.console.width = 65
        ui.console.height = 25
        ui._get_filtered_ifnames = Mock(return_value=['eth0'])
        ui._get_default_nic = Mock(return_value='eth0')
        ui._get_public_ipaddr = Mock(return_value='192.0.2.1')
        ui.appname = 'Test'
        return ui

    def test_successful_connection_refreshes_real_local_json_in_usage(self):
        import json
        disconnected = {'connection_status': 'disconnected', 'status': 'disconnected', 'services': {}}
        linked = {'connection_status': 'linked', 'status': 'ready', 'mode': 'hub',
                  'services': {'mail': {'enabled': True, 'status': 'active'},
                               'dns': {'enabled': True, 'hostname': 'test.tklapp.com'}}}
        local_states = iter((disconnected, linked))
        ui = self.make_ui()
        ui.console.actionbox.side_effect = ('ok', 'cancel')
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            if command == ['which', 'tklbam-status']:
                return subprocess.CompletedProcess(command, 0, '/usr/bin/tklbam-status\n', '')
            if command == ['/usr/bin/tklbam-status', '--short']:
                return subprocess.CompletedProcess(command, 11, 'not initialized\n', '')
            if command == ['/usr/lib/inithooks/bin/turnkey-hub', 'status', '--local', '--read-only', '--json']:
                return subprocess.CompletedProcess(command, 0, json.dumps(next(local_states)), '')
            if command == ['/usr/lib/inithooks/bin/hubservices.py', '--relink']:
                return subprocess.CompletedProcess(command, 0, '', '')
            self.fail('Unexpected command: %r' % command)
        with patch('confconsole.subprocess.run', side_effect=run), \
             patch('confconsole.notification_recipient', return_value='Security contact: Not set'), \
             patch.object(confconsole.ifutil, 'get_ipv6conf', return_value=(None, None)), \
             patch.object(confconsole.netinfo, 'get_hostname', return_value='test'):
            self.assertEqual(ui.usage(), 'connect_hub')
            self.assertEqual(ui.connect_hub(), 'usage')
            self.assertEqual(ui.usage(), 'advanced')
        first, second = [call.args for call in ui.console.actionbox.call_args_list]
        self.assertEqual(first[2], 'Connect to Hub')
        self.assertIn('Email delivery:  Not connected', first[1])
        self.assertIn('hub.turnkeylinux.org: Connected', second[1])
        self.assertIn('Email delivery:  Connected', second[1])
        self.assertIn('DNS:             Enabled in Hub', second[1])
        self.assertEqual(second[2], 'Set up backups')
        self.assertEqual(calls.count(['/usr/lib/inithooks/bin/turnkey-hub', 'status', '--local', '--read-only', '--json']), 2)

    def test_skip_with_zero_exit_remains_disconnected_after_refresh(self):
        import json
        ui = self.make_ui()
        ui.console.actionbox.side_effect = ('ok', 'cancel')
        status = {'connection_status': 'disconnected', 'status': 'disconnected', 'services': {}}
        def run(command, **kwargs):
            if command == ['which', 'tklbam-status']:
                return subprocess.CompletedProcess(command, 0, '/usr/bin/tklbam-status\n', '')
            if command == ['/usr/bin/tklbam-status', '--short']:
                return subprocess.CompletedProcess(command, 11, 'not initialized\n', '')
            if command == ['/usr/lib/inithooks/bin/turnkey-hub', 'status', '--local', '--read-only', '--json']:
                return subprocess.CompletedProcess(command, 0, json.dumps(status), '')
            if command == ['/usr/lib/inithooks/bin/hubservices.py', '--relink']:
                return subprocess.CompletedProcess(command, 0, '', '')
            self.fail('Unexpected command: %r' % command)
        with patch('confconsole.subprocess.run', side_effect=run), \
             patch('confconsole.notification_recipient', return_value='Security contact: Not set'), \
             patch.object(confconsole.ifutil, 'get_ipv6conf', return_value=(None, None)), \
             patch.object(confconsole.netinfo, 'get_hostname', return_value='test'):
            self.assertEqual(ui.usage(), 'connect_hub')
            self.assertEqual(ui.connect_hub(), 'usage')
            self.assertEqual(ui.usage(), 'advanced')
        second = ui.console.actionbox.call_args_list[1].args
        self.assertIn('hub.turnkeylinux.org: Not connected', second[1])
        self.assertEqual(second[2], 'Connect to Hub')
        self.assertEqual(ui.console.msgbox.call_count, 1)

    def test_cancelled_connection_returns_to_screen_without_error(self):
        ui = self.make_ui()
        with patch('confconsole.subprocess.run', return_value=subprocess.CompletedProcess([], 130)):
            self.assertEqual(ui.connect_hub(), 'usage')
        # The explanation precedes the shared flow. Cancellation should not
        # add a misleading failure or success message.
        self.assertEqual(ui.console.msgbox.call_count, 1)

    def test_connection_failure_returns_to_screen_with_recovery(self):
        ui = self.make_ui()
        with patch('confconsole.subprocess.run', return_value=subprocess.CompletedProcess([], 1)):
            self.assertEqual(ui.connect_hub(), 'usage')
        self.assertEqual(ui.console.msgbox.call_count, 2)
        self.assertIn('Try again', ui.console.msgbox.call_args.args[1])

    def test_back_from_disconnected_screen_never_starts_connection(self):
        import json
        ui = self.make_ui()
        ui.console.actionbox.return_value = 'cancel'
        def run(command, **kwargs):
            if command == ['which', 'tklbam-status']:
                return subprocess.CompletedProcess(command, 0, '/usr/bin/tklbam-status\n', '')
            if command == ['/usr/bin/tklbam-status', '--short']:
                return subprocess.CompletedProcess(command, 11, 'not initialized\n', '')
            if command == ['/usr/lib/inithooks/bin/turnkey-hub', 'status', '--local', '--read-only', '--json']:
                return subprocess.CompletedProcess(command, 0, json.dumps({'connection_status': 'disconnected'}), '')
            self.fail('Must not start connection: %r' % command)
        with patch('confconsole.subprocess.run', side_effect=run), \
             patch('confconsole.notification_recipient', return_value='Security contact: Not set'), \
             patch.object(confconsole.ifutil, 'get_ipv6conf', return_value=(None, None)), \
             patch.object(confconsole.netinfo, 'get_hostname', return_value='test'):
            self.assertEqual(ui.usage(), 'advanced')


class HubBackupAndManualMailTests(unittest.TestCase):
    def test_hub_backup_state_overrides_all_local_backup_states(self):
        local_backups = ('Backups: Ready to set up', 'Backups: Ready for first backup',
                         'TKLBAM: Backup ID #4, Updated Tue 2026-11-17 13:50')
        expected = {'disabled': 'Disabled in Hub', 'setup_required': 'Finish setup in Hub',
                    'migration_required': 'Migration required', 'unavailable': 'Needs attention',
                    'revoked': 'Needs attention'}
        for status, label in expected.items():
            for local in local_backups:
                with self.subTest(status=status, local=local):
                    state = {'connection_status': 'linked', 'services': {'backup': {'status': status}}}
                    self.assertIn('Backups:         ' + label, confconsole.hub_service_lines(state, local))
        for local in local_backups:
            state = {'connection_status': 'linked', 'services': {'backup': {'status': 'active'}}}
            expected_local = local.split(':', 1)[1].strip()
            self.assertIn('Backups:         ' + expected_local, confconsole.hub_service_lines(state, local))

    def test_disconnected_manual_smtp_has_its_own_state(self):
        states = [({'connection_status': 'disconnected', 'mail_preference': 'manual',
                    'mode': 'custom', 'status': 'ready'}, 'Custom SMTP'),
                  ({'connection_status': 'disconnected', 'mail_preference': 'manual',
                    'mode': '', 'status': 'disconnected'}, 'Needs attention'),
                  ({'connection_status': 'disconnected', 'status': 'disconnected'}, 'Not connected')]
        for state, label in states:
            with self.subTest(label=label):
                text = confconsole.hub_service_lines(state, 'Backups: Ready to set up')
                self.assertIn('hub.turnkeylinux.org: Not connected', text)
                self.assertIn('Email delivery:  ' + label, text)
                self.assertIn('DNS:             Not connected', text)

    def test_pending_domain_verification_is_not_connected(self):
        state = {'connection_status': 'linked', 'mode': 'hub', 'status': 'pending',
                 'services': {'mail': {'enabled': True, 'status': 'pending_verification'},
                              'dns': {'enabled': True}}}
        text = confconsole.hub_service_lines(state, 'Backups: Ready to set up')
        self.assertIn('Email delivery:  Waiting for domain verification', text)
        self.assertIn('DNS:             Enabled in Hub', text)

    def test_backup_attention_takes_user_to_help_even_when_local_id_exists(self):
        journey = HubServiceJourneyTests()
        backup_help = {'disabled': 'Enable backups for this server',
                       'setup_required': 'Finish backup setup',
                       'migration_required': 'Finish migrating'}
        local = [(0, 'TKLBAM: Backup ID #4'), (10, 'no backup'), (11, 'uninitialized')]
        for state, wording in backup_help.items():
            for code, status in local:
                with self.subTest(hub=state, local=code):
                    ui = journey.make_ui()
                    ui.console.actionbox.return_value = 'ok'
                    command_results = [subprocess.CompletedProcess([], 0, '/usr/bin/tklbam-status\n', ''),
                                       subprocess.CompletedProcess([], code, status, '')]
                    hub_state = {'connection_status': 'linked', 'services': {'backup': {'status': state}}}
                    with patch('confconsole.subprocess.run', side_effect=command_results), \
                         patch('confconsole.local_hub_status', return_value=hub_state), \
                         patch('confconsole.notification_recipient', return_value='Security contact: Not set'), \
                         patch.object(confconsole.ifutil, 'get_ipv6conf', return_value=(None, None)), \
                         patch.object(confconsole.netinfo, 'get_hostname', return_value='test'):
                        self.assertEqual(ui.usage(), 'backup_help')
                    self.assertEqual(ui.console.actionbox.call_args.args[2], 'Manage backups')
                    self.assertEqual(ui.backup_help(), 'usage')
                    self.assertIn(wording, ui.console.msgbox.call_args.args[1])


class ReadOnlyCompatibilityTests(unittest.TestCase):
    def test_old_helper_falls_back_only_when_option_is_unrecognized(self):
        old = subprocess.CompletedProcess([], 2, '', 'error: unrecognized arguments: --read-only')
        legacy = subprocess.CompletedProcess([], 0, '{"connection_status":"linked"}', '')
        with patch('confconsole.subprocess.run', side_effect=[old, legacy]) as run:
            self.assertEqual(confconsole.local_hub_status(), {'connection_status': 'linked'})
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[0].args[0],
                         ['/usr/lib/inithooks/bin/turnkey-hub', 'status', '--local', '--read-only', '--json'])
        self.assertEqual(run.call_args_list[1].args[0],
                         ['/usr/lib/inithooks/bin/turnkey-hub', 'status', '--local', '--json'])

    def test_other_failures_do_not_trigger_legacy_read(self):
        for message in ('permission denied', 'error: invalid configuration', ''):
            result = subprocess.CompletedProcess([], 1, '', message)
            with self.subTest(message=message), patch('confconsole.subprocess.run', return_value=result) as run:
                self.assertEqual(confconsole.local_hub_status(), {})
                self.assertEqual(run.call_count, 1)

    def test_read_only_success_never_runs_fallback(self):
        good = subprocess.CompletedProcess([], 0, '{"connection_status":"disconnected"}', '')
        with patch('confconsole.subprocess.run', return_value=good) as run:
            self.assertEqual(confconsole.local_hub_status()['connection_status'], 'disconnected')
            self.assertEqual(run.call_count, 1)
