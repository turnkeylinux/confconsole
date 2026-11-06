from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ifutil  # noqa: E402


class NetworkApplyTests(unittest.TestCase):
    def test_checked_force_reports_process_failure(self):
        failure = subprocess.CompletedProcess([], 1, '', 'resolver update failed')
        with patch.object(ifutil.subprocess, 'run', return_value=failure) as run:
            with self.assertLogs('ifutil', level='ERROR'):
                with self.assertRaisesRegex(ifutil.BadIfConfigError, 'resolver update failed'):
                    ifutil.ifup('eth0', force=True, check=True)
        self.assertEqual(run.call_args.args[0], ['/usr/sbin/ifup', '--force', 'eth0'])

    def test_recovery_force_keeps_existing_error_handling(self):
        failure = subprocess.CompletedProcess([], 1, '', 'recovery error')
        with patch.object(ifutil.subprocess, 'run', return_value=failure):
            self.assertEqual(ifutil.ifup('eth0', force=True), 'recovery error')

    def test_static_apply_cannot_succeed_on_an_address_after_ifup_failure(self):
        interfaces = Mock()
        failure = subprocess.CompletedProcess([], 1, '', 'resolver update failed')
        with patch.object(ifutil, 'ifdown'), \
             patch.object(ifutil, 'NetworkInterfaces', return_value=interfaces), \
             patch.object(ifutil, 'sleep'), \
             patch.object(ifutil.subprocess, 'run', return_value=failure), \
             patch.object(ifutil, 'InterfaceInfo', return_value=SimpleNamespace(address='192.0.2.12')) as info:
            with self.assertLogs('ifutil', level='ERROR'):
                error = ifutil.set_static('eth0', '192.0.2.12', '255.255.255.0',
                                          '192.0.2.1', ['2001:db8::53'])
        self.assertIn('resolver update failed', error)
        info.assert_not_called()

    def test_successful_static_apply_still_checks_assigned_address(self):
        interfaces = Mock()
        success = subprocess.CompletedProcess([], 0, '', '')
        with patch.object(ifutil, 'ifdown'), \
             patch.object(ifutil, 'NetworkInterfaces', return_value=interfaces), \
             patch.object(ifutil, 'sleep'), \
             patch.object(ifutil.subprocess, 'run', return_value=success), \
             patch.object(ifutil, 'InterfaceInfo', return_value=SimpleNamespace(address='192.0.2.12')):
            error = ifutil.set_static('eth0', '192.0.2.12', '255.255.255.0',
                                     '192.0.2.1', ['2001:db8::53'])
        self.assertIsNone(error)


if __name__ == '__main__':
    unittest.main()
