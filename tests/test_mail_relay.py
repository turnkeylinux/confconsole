"""App-email UI delegates privileged work and keeps secrets off argv."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mail_relay", ROOT / "plugins.d/Mail_Relaying/mail_relay.py")
wizard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wizard)


class MailRelayTest(unittest.TestCase):
    def setUp(self):
        self.console = Mock()
        self.console.width = 65
        self.addCleanup(patch.stopall)
        patch.object(wizard, "console", self.console, create=True).start()
        patch.object(wizard.os.path, "isfile", return_value=True).start()
        patch.object(wizard.shutil, "get_terminal_size", return_value=os.terminal_size((60, 24))).start()

    def test_linked_manual_smtp_uses_existing_connection_without_pairing(self):
        self.console.menu.return_value = ("ok", "Hub")
        with patch.object(wizard, "invoke", side_effect=[
                {"status": "ready", "connection_status": "linked", "mode": "custom", "host": "smtp.custom"},
                {"status": "ready", "connection_status": "linked"}]) as invoke:
            wizard.run()
        self.assertEqual(invoke.call_args_list[1].args, ("use-hub",))
        self.assertIn("Use Hub email", str(self.console.menu.call_args.args[2]))

    def test_linked_appliance_keeps_reconnect_available_for_revocation_recovery(self):
        self.console.menu.return_value = ("ok", "Reconnect")
        with patch.object(wizard, "invoke", return_value={"status": "ready", "connection_status": "linked", "mode": "hub"}), \
                patch.object(wizard, "connect") as connect:
            wizard.run()
        connect.assert_called_once_with()
        self.assertIn("Reconnect", [item[0] for item in self.console.menu.call_args.args[2]])
        self.assertEqual("Sync", self.console.menu.call_args.args[2][0][0])

    def test_disconnected_menu_hides_irrelevant_test_and_disconnect(self):
        self.console.menu.return_value = ("cancel", "")
        with patch.object(wizard, "invoke", return_value={"status": "disconnected"}) as invoke:
            wizard.run()
        self.assertEqual([item[0] for item in self.console.menu.call_args.args[2]], ["Hub", "Custom"])
        invoke.assert_called_once_with("status", "--local")
        self.assertEqual(self.console.width, 65)

    def test_cancel_does_not_change_existing_relay(self):
        self.console.menu.return_value = ("cancel", "")
        with patch.object(wizard, "invoke", return_value={"status": "ready", "host": "smtp.example"}) as invoke:
            wizard.run()
        invoke.assert_called_once_with("status", "--local")

    def test_pairing_pending_then_success_keeps_action_obvious(self):
        self.console._wrapper.return_value = "ok"
        with patch.object(wizard, "invoke", side_effect=[
            {"verification_uri": "https://hub.turnkeylinux.org/link", "user_code": "D34C-F5A9"},
            {"status": "pending"}, {"status": "ready", "domain": "sample.tklapp.com"},
        ]):
            wizard.connect()
        self.assertIn("Waiting for approval", self.console._wrapper.call_args.args[1])
        self.assertIn("backups and migration", self.console.msgbox.call_args.args[1])

    def test_pairing_expired_denied_and_error_have_recovery(self):
        for status in ("expired", "denied", "error"):
            with self.subTest(status=status):
                self.console._wrapper.return_value = "ok"
                with patch.object(wizard, "invoke", side_effect=[
                    {"verification_uri": "https://hub.turnkeylinux.org/link", "user_code": "D34C-F5A9"},
                    {"status": status, "message": "Try again from the Hub."},
                ]):
                    wizard.connect()
                self.assertTrue(self.console.msgbox.called)

    def test_pairing_cancel_never_polls_or_reconfigures(self):
        self.console._wrapper.return_value = "cancel"
        with patch.object(wizard, "invoke", return_value={"verification_uri": "https://hub.turnkeylinux.org/link", "user_code": "D34C-F5A9"}) as invoke:
            wizard.connect()
        invoke.assert_called_once_with("connect", "--start")

    def test_link_prompt_uses_browser_code_with_two_clear_actions(self):
        self.console._wrapper.return_value = "cancel"
        with patch.object(wizard, "invoke", return_value={
                "verification_uri": "https://hub.turnkeylinux.org/link", "user_code": "D34C-F5A9"}):
            wizard.connect()
        call = self.console._wrapper.call_args
        self.assertEqual(call.args[0], "yesno")
        self.assertIn("https://hub.turnkeylinux.org/link\n\nEnter this code:\n\nD34C-F5A9", call.args[1])
        self.assertEqual(call.kwargs["yes_label"], "Check connection")
        self.assertEqual(call.kwargs["no_label"], "Back")
        self.assertLessEqual(call.kwargs["width"], 56)
        self.assertLessEqual(call.kwargs["height"], 22)
        self.assertNotIn("mail settings", call.args[1])
        self.assertIn("backups and migration", wizard.TEXT)

    def test_custom_form_masks_password_and_sends_it_only_through_stdin(self):
        self.console._wrapper.return_value = ("ok", ["smtp.example.net", "587", "user", "private-password"])
        response = subprocess.CompletedProcess([], 0, stdout=json.dumps({"status": "ready"}), stderr="")
        with patch.object(wizard.subprocess, "run", return_value=response) as run:
            wizard.custom()
        fields = self.console._wrapper.call_args.args[2]
        self.assertEqual(fields[-1][-1], 1)
        self.assertLessEqual(fields[-1][-3], 37)
        self.assertNotIn("private-password", repr(run.call_args.args[0]))
        self.assertEqual(run.call_args.args[0][0], "/usr/lib/inithooks/bin/turnkey-hub")
        self.assertEqual(json.loads(run.call_args.kwargs["input"])["password"], "private-password")
        self.assertNotIn("private-password", repr(self.console.msgbox.call_args_list))

    def test_custom_cancel_and_invalid_input_never_apply(self):
        self.console._wrapper.side_effect = [("ok", ["smtp.example", "invalid", "user", "secret"]), ("cancel", [])]
        with patch.object(wizard, "invoke") as invoke:
            wizard.custom()
        invoke.assert_not_called()
        self.assertIn("port", self.console.msgbox.call_args.args[1])

    def test_reset_mail_does_not_request_full_device_reset(self):
        self.console.menu.return_value = ("ok", "Reset mail")
        self.console.yesno.return_value = "ok"
        with patch.object(wizard, "invoke", side_effect=[
            {"status": "ready", "host": "smtp.example"}, {"status": "disconnected"},
        ]) as invoke:
            wizard.run()
        self.assertEqual(invoke.call_args.args, ("reset-mail",))
        self.assertIn("dynamic DNS", self.console.yesno.call_args.args[0])
        self.assertIn("dynamic DNS are unchanged", self.console.msgbox.call_args.args[1])

    def test_helper_failure_does_not_echo_stderr(self):
        response = subprocess.CompletedProcess([], 1, stdout="not-json", stderr="private-password")
        with patch.object(wizard.subprocess, "run", return_value=response):
            result = wizard.invoke("status")
        self.assertEqual(result["status"], "error")
        self.assertNotIn("private-password", repr(result))

    def test_missing_helper_has_actionable_package_recovery(self):
        with patch.object(wizard.os.path, "isfile", return_value=False):
            wizard.run()
        self.assertIn("inithooks", self.console.msgbox.call_args.args[1])
        self.console.menu.assert_not_called()


if __name__ == "__main__":
    unittest.main()
