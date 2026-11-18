"""Ctrl-C and Escape confirm exit and preserve the active dialog."""
import unittest
from unittest.mock import Mock

import confconsole


class ConsoleInterruptTests(unittest.TestCase):
    def setUp(self):
        self.ui = confconsole.Console.__new__(confconsole.Console)
        self.ui.width, self.ui.height = 65, 25
        self.ui.console = Mock()
        self.ui.console.OK = 'ok'

    def test_cancel_interrupt_reopens_same_dialog(self):
        self.ui.console.msgbox.side_effect = [KeyboardInterrupt, 'ok']
        self.ui.console.yesno.return_value = 'cancel'
        self.assertEqual(self.ui.msgbox('Title', 'Content'), 'ok')
        self.assertEqual(self.ui.console.msgbox.call_count, 2)
        self.ui.console.yesno.assert_called_once_with('\n    Do you really want to quit?', height=7, width=39)

    def test_confirm_interrupt_exits_with_130(self):
        self.ui.console.msgbox.side_effect = KeyboardInterrupt
        self.ui.console.yesno.return_value = 'ok'
        with self.assertRaises(SystemExit) as caught:
            self.ui.msgbox('Title', 'Content')
        self.assertEqual(caught.exception.code, 130)

    def test_repeated_interrupt_dismisses_confirmation(self):
        self.ui.console.msgbox.side_effect = [KeyboardInterrupt, 'ok']
        self.ui.console.yesno.side_effect = KeyboardInterrupt
        self.assertEqual(self.ui.msgbox('Title', 'Content'), 'ok')

    def test_cancel_interrupt_outside_dialog_returns_to_usage(self):
        ui = confconsole.TurnkeyConsole.__new__(confconsole.TurnkeyConsole)
        ui.console = Mock()
        ui.usage = Mock(side_effect=[KeyboardInterrupt, None])
        ui.loop()
        self.assertEqual(ui.usage.call_count, 2)
        ui.console.confirm_quit.assert_called_once_with()

    def test_escape_also_exits_with_130(self):
        self.ui.console.msgbox.return_value = 'esc'
        self.ui.console.yesno.return_value = 'ok'
        with self.assertRaises(SystemExit) as caught:
            self.ui.msgbox('Title', 'Content')
        self.assertEqual(caught.exception.code, 130)


if __name__ == '__main__':
    unittest.main()
