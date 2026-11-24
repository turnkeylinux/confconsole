"""Exercise the shared installer through a real terminal."""
import importlib.util
import os
import pty
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


class SecurityUpdateTerminalTests(unittest.TestCase):
    def exercise(self, exit_code):
        with tempfile.TemporaryDirectory() as directory:
            updater = Path(directory) / 'turnkey-install-security-updates'
            updater.write_text('#!/bin/sh\nprintf "live updater output\\n"\nprintf "detail on stderr\\n" >&2\nexit %d\n' % exit_code)
            updater.chmod(0o755)
            master, slave = pty.openpty()
            process = subprocess.Popen(
                [sys.executable, '-c', 'from security_update_runner import run_security_updates; run_security_updates()'],
                cwd=ROOT, stdin=slave, stdout=slave, stderr=slave,
                env=dict(os.environ, PATH=directory + os.pathsep + os.environ.get('PATH', '')),
            )
            os.close(slave)
            self.addCleanup(lambda: os.close(master))
            self.addCleanup(lambda: process.kill() if process.poll() is None else None)
            output = b''
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], .1)
                if ready:
                    try:
                        output += os.read(master, 4096)
                    except OSError:
                        break
                if exit_code and b'Press Enter' in output:
                    self.assertIsNone(process.poll(), 'failure must wait for Enter')
                    os.write(master, b'\n')
                    break
                if process.poll() is not None:
                    break
            self.assertEqual(process.wait(timeout=5), 0)
            self.assertIn(b'\x1b[2J\x1b[H', output)
            self.assertIn(b'live updater output', output)
            self.assertIn(b'detail on stderr', output)
            return output

    def test_success_streams_output_and_returns_without_prompt(self):
        self.assertNotIn(b'Press Enter', self.exercise(0))

    def test_failure_shows_diagnostics_until_enter(self):
        output = self.exercise(2)
        self.assertIn(b'sudo security-updates --status', output)
        self.assertIn(b'Press Enter', output)

    def test_advanced_menu_uses_the_same_terminal_flow(self):
        path = ROOT / 'plugins.d/System_Settings/Security_updates/Security_Update.py'
        spec = importlib.util.spec_from_file_location('security_update_plugin', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module, 'run_security_updates') as runner:
            module.run()
        runner.assert_called_once_with()
