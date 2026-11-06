import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import confconsole  # noqa: E402


class FormConsole:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.forms = []
        self.messages = []

    def form(self, title, text, fields, **options):
        self.forms.append((fields, options))
        response = next(self.responses)
        return ('ok', [field[3] for field in fields]) if response == 'retain' else response

    def msgbox(self, title, text, **options):
        self.messages.append((title, text, options))


class StaticNetworkFormTests(unittest.TestCase):
    def run_form(self, responses, resolvers=None, columns=80, apply_result=None):
        ui = confconsole.TurnkeyConsole.__new__(confconsole.TurnkeyConsole)
        ui.ifname = 'eth0'
        ui.console = FormConsole(responses)
        current = ('192.0.2.10', '255.255.255.0', '192.0.2.1',
                   resolvers or ['192.0.2.53'])
        with patch.object(confconsole.ifutil, 'get_ipconf', return_value=current), \
             patch.object(confconsole.ifutil, 'set_static', return_value=apply_result) as apply, \
             patch.object(confconsole, 'get_terminal_size', return_value=os.terminal_size((columns, 24))), \
             patch.dict(os.environ, {}, clear=True):
            result = ui._ifconf_staticip()
        return ui.console, apply, result

    def test_retained_ipv6_resolver_passes_validation(self):
        resolver = '2001:4860:4860::8888'
        console, apply, _ = self.run_form(['retain'], resolvers=[resolver])
        apply.assert_called_once_with('eth0', '192.0.2.10', '255.255.255.0',
                                      '192.0.2.1', [resolver])
        self.assertEqual(console.messages, [])

    def test_full_ipv6_and_scoped_resolver_inputs_fit(self):
        resolvers = ['ffff:ffff:ffff:ffff:ffff:ffff:255.255.255.255',
                     'fe80:0000:0000:0000:0000:0000:0000:0001%interface12345']
        for resolver in resolvers:
            with self.subTest(resolver=resolver):
                console, apply, _ = self.run_form(['retain'], resolvers=[resolver])
                self.assertEqual(apply.call_args.args[-1], [resolver])
                fields = console.forms[0][0]
                self.assertGreaterEqual(fields[3][-1], len(resolver))
                self.assertEqual([field[-1] for field in fields[:3]], [15, 15, 15])

    def test_cancel_does_not_apply(self):
        _, apply, result = self.run_form([('cancel', [])])
        apply.assert_not_called()
        self.assertEqual(result, 'ifconf')

    def test_invalid_input_is_retained_until_corrected(self):
        invalid = ['192.0.2.11', '255.255.255.0', '192.0.2.1', 'invalid', '']
        corrected = invalid[:3] + ['2001:4860:4860::8888', '']
        console, apply, _ = self.run_form([('ok', invalid), ('ok', corrected)])
        self.assertEqual([field[3] for field in console.forms[1][0]], invalid)
        self.assertIn('Invalid nameserver: invalid', console.messages[0][1])
        self.assertTrue(console.messages[0][2]['autosize'])
        apply.assert_called_once_with('eth0', *corrected[:3], [corrected[3]])

    def test_apply_error_preserves_edits_for_retry_or_cancel(self):
        edited = ['192.0.2.12', '255.255.255.0', '192.0.2.1', '2001:db8::53', '']
        console, apply, _ = self.run_form([('ok', edited), ('cancel', [])],
                                          apply_result='Resolver configuration failed')
        self.assertEqual(apply.call_count, 1)
        self.assertEqual([field[3] for field in console.forms[1][0]], edited)
        self.assertIn('Resolver configuration failed', console.messages[0][1])

    def test_form_uses_available_width_and_autosizing(self):
        for columns in [60, 80, 120]:
            with self.subTest(columns=columns):
                console, _, _ = self.run_form([('cancel', [])], columns=columns)
                fields, options = console.forms[0]
                self.assertTrue(options['autosize'])
                self.assertLessEqual(max(field[5] + field[6] for field in fields), columns - 8)


if __name__ == '__main__':
    unittest.main()
