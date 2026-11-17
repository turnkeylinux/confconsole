"""Navigation of empty, single-item, and multi-item plugin directories."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import plugin


class NavigationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.console = Mock()

    def script(self, directory, name, body='def run():\n    pass\n'):
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (name + '.py')
        path.write_text(body)
        path.chmod(0o755)
        return path

    def manager(self):
        result = plugin.PluginManager(str(self.root), {})
        result.updateGlobals({'console': self.console})
        return result

    def test_single_plugin_opens_directly_and_returns_to_advanced(self):
        directory = self.root / 'Hub_services'
        path = self.script(directory, 'hub_services')
        (directory / 'helper.sh').write_text('helper')
        m = self.manager()
        self.assertEqual(m.path_map[str(directory)].run(), str(path))
        self.console.menu.assert_not_called()
        self.assertEqual(m.path_map[str(path)].run(), 'advanced')

    def test_nested_collapsed_directories_return_to_visible_menu(self):
        visible = self.root / 'Visible'
        path = self.script(visible / 'Only' / 'Nested', 'action')
        self.script(visible, 'other')
        m = self.manager()
        self.assertEqual(m.path_map[str(visible / 'Only')].run(), str(visible / 'Only' / 'Nested'))
        self.assertEqual(m.path_map[str(visible / 'Only' / 'Nested')].run(), str(path))
        self.assertEqual(m.path_map[str(path)].run(), str(visible))
        self.console.menu.return_value = ('cancel', '')
        self.assertEqual(m.path_map[str(visible)].run(), 'advanced')
        self.assertEqual(len(self.console.menu.call_args.args[2]), 2)

    def test_empty_directory_shows_message_then_returns(self):
        directory = self.root / 'Empty'
        directory.mkdir()
        m = self.manager()
        self.assertEqual(m.path_map[str(directory)].run(), 'advanced')
        self.console.msgbox.assert_called_once()
        self.console.menu.assert_not_called()

    def test_non_selectable_python_file_does_not_count(self):
        directory = self.root / 'Section'
        path = self.script(directory, 'action')
        self.script(directory, 'helper', 'value = 1\n')
        m = self.manager()
        self.assertEqual(m.path_map[str(directory)].run(), str(path))
        self.assertEqual(m.path_map[str(path)].run(), 'advanced')

if __name__ == '__main__':
    unittest.main()
