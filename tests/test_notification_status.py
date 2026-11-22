"""System notification recipient shown on the usage screen."""
from pathlib import Path
import tempfile
import unittest

import confconsole


class NotificationStatusTest(unittest.TestCase):
    def test_recipient_and_unset_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'aliases'
            self.assertEqual(confconsole.notification_recipient(path), 'Security contact: Not set')
            path.write_text('postmaster: root\nroot: localuser\n')
            self.assertEqual(confconsole.notification_recipient(path), 'Security contact: Not set')
            path.write_text('postmaster: root\nroot: person@example.net\n')
            self.assertEqual(confconsole.notification_recipient(path), 'Security contact: person@example.net')
