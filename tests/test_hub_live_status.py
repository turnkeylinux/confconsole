"""One-shot Hub status refreshes and the result shown on the main screen."""
import subprocess
import unittest
from unittest.mock import Mock, patch

import confconsole
from test_mail_relay import wizard


class LiveHubStatusTests(unittest.TestCase):
    first = 'a' * 32
    next = 'b' * 32

    def setUp(self):
        self.console = confconsole.TurnkeyConsole.__new__(confconsole.TurnkeyConsole)
        self.console.console = Mock()

    def local(self, device):
        return {'connection_status': 'linked', 'device_id': device,
                'mode': 'hub', 'status': 'ready',
                'services': {'mail': {'enabled': True}, 'dns': {'enabled': True}}}

    def remote(self, device):
        return {'connection_status': 'linked', 'device_id': device,
                'services': {'mail': {'enabled': False, 'status': 'disabled'},
                             'dns': {'enabled': True, 'hostname': 'next.tklapp.com'},
                             'backup': {'requested': False}}}

    def test_pending_setup_waits_then_reads_completed_state(self):
        pending = dict(self.local(self.first), setup_pending=True)
        ready = dict(self.local(self.first), setup_pending=False)
        with patch('confconsole.local_hub_status', side_effect=[pending, ready]), \
             patch('confconsole.remote_hub_status', return_value=self.remote(self.first)), \
             patch('confconsole.subprocess.run', return_value=subprocess.CompletedProcess([], 0)) as run:
            result = self.console.main_hub_state()
        run.assert_called_once_with(['systemctl', 'start', 'turnkey-hub-provision.service'],
                                    capture_output=True, text=True, timeout=90)
        self.console.console.infobox.assert_called_once_with('Finishing Hub setup...')
        self.console.console.msgbox.assert_not_called()
        self.assertFalse(result['setup_pending'])

    def test_failed_setup_is_reported_once_and_main_screen_remains_available(self):
        pending = dict(self.local(self.first), setup_pending=True)
        with patch('confconsole.local_hub_status', return_value=pending), \
             patch('confconsole.remote_hub_status', return_value=self.remote(self.first)), \
             patch('confconsole.subprocess.run', return_value=subprocess.CompletedProcess([], 1)) as run:
            self.console.main_hub_state()
            self.console.main_hub_state()
        run.assert_called_once()
        self.console.console.msgbox.assert_called_once()

    def test_completed_setup_does_not_show_progress(self):
        with patch('confconsole.local_hub_status', return_value=self.local(self.first)), \
             patch('confconsole.remote_hub_status', return_value=self.remote(self.first)), \
             patch('confconsole.subprocess.run') as run:
            self.console.main_hub_state()
        run.assert_not_called()
        self.console.console.infobox.assert_not_called()

    def test_pending_state_after_service_exit_reports_failure(self):
        pending = dict(self.local(self.first), setup_pending=True)
        with patch('confconsole.local_hub_status', return_value=pending), \
             patch('confconsole.remote_hub_status', return_value=self.remote(self.first)), \
             patch('confconsole.subprocess.run', return_value=subprocess.CompletedProcess([], 0)):
            self.console.main_hub_state()
        self.console.console.msgbox.assert_called_once()

    def test_provision_timeout_reports_failure(self):
        pending = dict(self.local(self.first), setup_pending=True)
        with patch('confconsole.local_hub_status', return_value=pending), \
             patch('confconsole.remote_hub_status', return_value=self.remote(self.first)), \
             patch('confconsole.subprocess.run', side_effect=subprocess.TimeoutExpired('systemctl', 90)):
            self.console.main_hub_state()
        self.console.console.msgbox.assert_called_once()

    def test_initial_and_post_pairing_requests_are_once_per_connection(self):
        unlinked = {'connection_status': 'disconnected'}
        linked = self.local(self.first)
        relinked = self.local(self.next)
        with patch('confconsole.local_hub_status',
                   side_effect=[unlinked, unlinked, linked, linked, relinked, relinked]), \
             patch('confconsole.remote_hub_status',
                   side_effect=[self.remote(self.first), self.remote(self.next)]) as refresh:
            self.assertEqual(self.console.main_hub_state(), unlinked)
            self.assertEqual(self.console.main_hub_state(), unlinked)
            refresh.assert_not_called()
            for expected in (1, 1, 2, 2):
                state = self.console.main_hub_state()
                self.assertTrue(state['hub_status_refreshed'])
                self.assertEqual(refresh.call_count, expected)

    def test_connection_revoked_after_launch_still_offers_reconnect_on_redraw(self):
        with patch('confconsole.local_hub_status', return_value=self.local(self.first)), \
             patch('confconsole.remote_hub_status', return_value={
                 'connection_status': 'disconnected', 'device_id': self.first,
             }) as refresh:
            for _ in range(2):
                state = self.console.main_hub_state()
                self.assertEqual(state['connection_status'], 'disconnected')
                self.assertIn('Disconnected in Hub', confconsole.hub_service_lines(state, ''))
            refresh.assert_called_once_with()

    def test_remote_status_unavailable_preserves_local_services_without_polling(self):
        with patch('confconsole.local_hub_status', return_value=self.local(self.first)), \
             patch('confconsole.remote_hub_status', return_value={}) as refresh:
            for _ in range(2):
                state = self.console.main_hub_state()
                text = confconsole.hub_service_lines(state, '', dns_hostname='old.tklapp.com')
                self.assertIn('hub.turnkeylinux.org: Status unavailable', text)
                self.assertIn('Yes, via TurnKey Hub', text)
                self.assertIn('old.tklapp.com', text)
            refresh.assert_called_once_with()

    def test_remote_flags_and_dns_assignment_do_not_claim_local_setup(self):
        local = self.local(self.first)
        state = confconsole.merge_hub_snapshot(local, self.remote(self.first), self.first)
        pending = confconsole.hub_service_lines(state, 'Backup ID #1', dns_hostname='old.tklapp.com')
        self.assertIn('Email delivery:    Disabled', pending)
        self.assertIn('old.tklapp.com', pending)
        self.assertNotIn('Pending:', pending)
        self.assertIn('Last: Backup ID #1', pending)
        applied = confconsole.hub_service_lines(state, 'Backup ID #1', dns_hostname='next.tklapp.com')
        self.assertIn('Dynamic DNS:     next.tklapp.com', applied)
        self.assertNotIn('Pending:', applied)
        self.assertTrue(local['services']['mail']['enabled'])

    def test_partial_response_cannot_turn_local_hostname_into_pending_assignment(self):
        local = self.local(self.first)
        local['services']['dns']['hostname'] = 'cached.tklapp.com'
        for services in ({}, {'dns': {'enabled': True}},):
            with self.subTest(services=services):
                state = confconsole.merge_hub_snapshot(local, {
                    'device_id': self.first, 'connection_status': 'linked', 'services': services,
                }, self.first)
                self.assertTrue(state['hub_status_unavailable'])
                self.assertNotIn('Pending:', confconsole.hub_service_lines(state, ''))
        response = self.remote(self.first)
        response['services']['dns']['hostname'] = 'invalid.example'
        state = confconsole.merge_hub_snapshot(local, response, self.first)
        self.assertNotIn('Pending:', confconsole.hub_service_lines(state, ''))

    def test_newly_applied_registry_hostname_supersedes_session_pending_assignment(self):
        with patch('confconsole.local_hub_status', return_value=self.local(self.first)), \
             patch('confconsole.remote_hub_status', return_value=self.remote(self.first)) as refresh, \
             patch('confconsole.local_dynamic_dns_hostname',
                   side_effect=['old.tklapp.com', 'latest.tklapp.com', 'old.tklapp.com']), \
             patch('confconsole.subprocess.run') as update:
            for expected in ('latest.tklapp.com', 'old.tklapp.com'):
                state = self.console.main_hub_state()
                hostname = self.console.main_dns_hostname(state)
                rendered = confconsole.hub_service_lines(state, '', dns_hostname=hostname)
                self.assertIn(expected, rendered)
                self.assertNotIn('Pending:', rendered)
            refresh.assert_called_once_with()
            update.assert_not_called()

    def test_changed_hostname_updates_once_and_displays_applied_name(self):
        with patch('confconsole.local_hub_status', return_value=self.local(self.first)), \
             patch('confconsole.remote_hub_status', return_value=self.remote(self.first)), \
             patch('confconsole.local_dynamic_dns_hostname',
                   side_effect=['old.tklapp.com', 'old.tklapp.com',
                                'next.tklapp.com', 'next.tklapp.com']), \
             patch('confconsole.subprocess.run') as update:
            for _ in range(2):
                state = self.console.main_hub_state()
                hostname = self.console.main_dns_hostname(state)
                self.assertEqual(hostname, 'next.tklapp.com')
                self.assertNotIn('Update failed', confconsole.hub_service_lines(state, '', dns_hostname=hostname))
            update.assert_called_once_with(
                ['/usr/bin/hubdns-update', '--quiet'], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=True)

    def test_failed_update_reports_scheduled_retry_without_repeating_on_redraw(self):
        for error in (OSError(), subprocess.TimeoutExpired('hubdns-update', 5),
                      subprocess.CalledProcessError(1, 'hubdns-update')):
            with self.subTest(error=error):
                self.console = confconsole.TurnkeyConsole.__new__(confconsole.TurnkeyConsole)
                self.console.console = Mock()
                with patch('confconsole.local_hub_status', return_value=self.local(self.first)), \
                     patch('confconsole.remote_hub_status', return_value=self.remote(self.first)), \
                     patch('confconsole.local_dynamic_dns_hostname', return_value='old.tklapp.com'), \
                     patch('confconsole.subprocess.run', side_effect=error) as update:
                    for _ in range(2):
                        state = self.console.main_hub_state()
                        hostname = self.console.main_dns_hostname(state)
                        text = confconsole.hub_service_lines(state, '', dns_hostname=hostname)
                        self.assertIn('Update failed, retry scheduled', text)
                        self.assertIn('old.tklapp.com', text)
                        self.assertNotIn('Pending:', text)
                    update.assert_called_once()

    def test_missing_or_matching_local_hostname_never_triggers_update(self):
        for local_name in ('', 'next.tklapp.com'):
            with self.subTest(local_name=local_name):
                self.console = confconsole.TurnkeyConsole.__new__(confconsole.TurnkeyConsole)
                with patch('confconsole.local_hub_status', return_value=self.local(self.first)), \
                     patch('confconsole.remote_hub_status', return_value=self.remote(self.first)), \
                     patch('confconsole.local_dynamic_dns_hostname', return_value=local_name), \
                     patch('confconsole.subprocess.run') as update:
                    state = self.console.main_hub_state()
                    self.assertEqual(self.console.main_dns_hostname(state), local_name)
                    update.assert_not_called()

    def test_scheduled_success_clears_a_previous_update_failure(self):
        with patch('confconsole.local_hub_status', return_value=self.local(self.first)), \
             patch('confconsole.remote_hub_status', return_value=self.remote(self.first)), \
             patch('confconsole.local_dynamic_dns_hostname', side_effect=[
                 'old.tklapp.com', 'old.tklapp.com', 'old.tklapp.com', 'next.tklapp.com']), \
             patch('confconsole.subprocess.run', side_effect=OSError()) as update:
            state = self.console.main_hub_state()
            hostname = self.console.main_dns_hostname(state)
            self.assertIn('Update failed', confconsole.hub_service_lines(state, '', dns_hostname=hostname))
            state = self.console.main_hub_state()
            hostname = self.console.main_dns_hostname(state)
            self.assertEqual(hostname, 'next.tklapp.com')
            self.assertNotIn('Update failed', confconsole.hub_service_lines(state, '', dns_hostname=hostname))
            update.assert_called_once()

    def test_explicit_hub_services_refresh_replaces_the_main_screen_snapshot(self):
        for choice in ('Status', 'Hub'):
            with self.subTest(choice=choice), \
                 patch('confconsole.local_hub_status', return_value=self.local(self.first)), \
                 patch('confconsole.remote_hub_status', return_value=self.remote(self.first)) as refresh, \
                 patch.object(wizard, 'remember_hub_status', self.console.remember_hub_status), \
                 patch.object(wizard, 'console', create=True) as ui, \
                 patch.object(wizard, 'message'), patch.object(wizard.os.path, 'isfile', return_value=True):
                self.console._hub_status_device = None
                ui.width = 65
                ui.height = 25
                ui.menu.return_value = ('ok', choice)
                start = self.console.main_hub_state()
                self.assertEqual(start['hub_dns_assignment'], 'next.tklapp.com')
                self.assertFalse(start['services']['mail']['enabled'])
                updated = self.remote(self.first)
                updated['services']['dns']['hostname'] = 'renamed.tklapp.com'
                updated['services']['mail'] = {'enabled': True, 'status': 'active'}
                updated['services']['backup']['requested'] = True
                with patch.object(wizard, 'invoke', side_effect=[self.local(self.first), updated]) as invoke:
                    wizard.run()
                self.assertEqual(invoke.call_args.args, ('status' if choice == 'Status' else 'use-hub',))
                current = self.console.main_hub_state()
                self.assertEqual(current['hub_dns_assignment'], 'renamed.tklapp.com')
                self.assertTrue(current['services']['mail']['enabled'])
                self.assertNotIn('status', current['services']['backup'])
                refresh.assert_called_once_with()

    def test_remote_lookup_uses_only_the_bounded_display_command(self):
        with patch('confconsole.subprocess.run', side_effect=subprocess.TimeoutExpired('status', 3)) as run:
            self.assertEqual(confconsole.remote_hub_status(), {})
        run.assert_called_once_with(
            ['/usr/lib/inithooks/bin/turnkey-hub', 'connection-status', '--json'],
            capture_output=True, text=True, timeout=3, check=True,
        )
