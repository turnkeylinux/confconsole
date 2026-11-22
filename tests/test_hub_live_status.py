"""One-shot Hub status refreshes and the result shown on the main screen."""
import subprocess
import unittest
from unittest.mock import patch

import confconsole
from test_mail_relay import wizard


class LiveHubStatusTests(unittest.TestCase):
    first = 'a' * 32
    next = 'b' * 32

    def setUp(self):
        self.console = confconsole.TurnkeyConsole.__new__(confconsole.TurnkeyConsole)

    def local(self, device):
        return {'connection_status': 'linked', 'device_id': device,
                'mode': 'hub', 'status': 'ready',
                'services': {'mail': {'enabled': True}, 'dns': {'enabled': True}}}

    def remote(self, device):
        return {'connection_status': 'linked', 'device_id': device,
                'services': {'mail': {'enabled': False, 'status': 'disabled'},
                             'dns': {'enabled': True, 'hostname': 'next.tklapp.com'},
                             'backup': {'requested': False}}}

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
                self.assertIn('Via TurnKey Hub', text)
                self.assertIn('old.tklapp.com', text)
            refresh.assert_called_once_with()

    def test_remote_flags_and_dns_assignment_do_not_claim_local_setup(self):
        local = self.local(self.first)
        state = confconsole.merge_hub_snapshot(local, self.remote(self.first), self.first)
        pending = confconsole.hub_service_lines(state, 'Backup ID #1', dns_hostname='old.tklapp.com')
        self.assertIn('Email delivery:    Disabled', pending)
        self.assertIn('Pending: next.tklapp.com', pending)
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
                   side_effect=['old.tklapp.com', 'old.tklapp.com', 'latest.tklapp.com', 'old.tklapp.com']):
            for expected in ('Pending: next.tklapp.com', 'latest.tklapp.com', 'old.tklapp.com'):
                state = self.console.main_hub_state()
                hostname = self.console.main_dns_hostname(state)
                rendered = confconsole.hub_service_lines(state, '', dns_hostname=hostname)
                self.assertIn(expected, rendered)
                if not expected.startswith('Pending:'):
                    self.assertNotIn('Pending:', rendered)
            refresh.assert_called_once_with()

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
