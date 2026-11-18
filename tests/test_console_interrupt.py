"""Ctrl-C offers a choice to leave or return to the console."""
import unittest
from unittest.mock import Mock

import confconsole


class ConsoleInterruptTests(unittest.TestCase):
    def console(self, answer):
        ui = confconsole.TurnkeyConsole.__new__(confconsole.TurnkeyConsole)
        ui.console = Mock()
        ui.console.yesno.return_value = answer
        ui.usage = Mock(side_effect=[KeyboardInterrupt, None])
        return ui

    def test_quit_after_interrupt(self):
        ui = self.console('ok')
        ui.loop()
        self.assertEqual(ui.usage.call_count, 1)
        self.assertEqual(ui.console.yesno.call_args.kwargs['ok_label'], 'Quit')

    def test_stay_after_interrupt_returns_to_usage(self):
        ui = self.console('cancel')
        ui.loop()
        self.assertEqual(ui.usage.call_count, 2)
        self.assertEqual(ui.console.yesno.call_args.kwargs['cancel_label'], 'Stay')


if __name__ == '__main__':
    unittest.main()
