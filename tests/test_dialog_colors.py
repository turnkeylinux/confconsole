"""Console defaults preserve administrator-selected dialog themes."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import confconsole


class DialogConfigTests(unittest.TestCase):
    def test_packaged_palette_is_used_without_custom_theme(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(confconsole.os.path, 'expanduser', return_value='/home/test/.dialogrc'), \
             patch.object(confconsole.os.path, 'isfile', side_effect=lambda p: str(p).endswith('/conf/dialogrc')):
            self.assertTrue(confconsole.dialog_config().endswith('/conf/dialogrc'))

    def test_existing_theme_is_preserved(self):
        with patch.dict(os.environ, {'DIALOGRC': '/custom/theme'}, clear=True):
            self.assertIsNone(confconsole.dialog_config())
        with patch.dict(os.environ, {}, clear=True), patch.object(confconsole.os.path, 'isfile', return_value=True):
            self.assertIsNone(confconsole.dialog_config())

    def test_missing_packaged_palette_uses_dialog_defaults(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(confconsole.os.path, 'isfile', return_value=False):
            self.assertIsNone(confconsole.dialog_config())
