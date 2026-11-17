"""App-email UI delegates privileged work and keeps secrets off argv."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mail_relay", ROOT / "plugins.d/Hub_services/hub_services.py")
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
        self.assertEqual("Status", self.console.menu.call_args.args[2][0][0])

    def test_disconnected_menu_hides_irrelevant_test_and_disconnect(self):
        self.console.menu.return_value = ("cancel", "")
        with patch.object(wizard, "invoke", return_value={"status": "disconnected"}) as invoke:
            wizard.run()
        self.assertEqual([item[0] for item in self.console.menu.call_args.args[2]], ["Hub"])
        invoke.assert_called_once_with("status", "--local")
        self.assertEqual(self.console.width, 65)

    def test_cancel_does_not_change_existing_relay(self):
        self.console.menu.return_value = ("cancel", "")
        with patch.object(wizard, "invoke", return_value={"status": "ready", "host": "smtp.example"}) as invoke:
            wizard.run()
        invoke.assert_called_once_with("status", "--local")

    def test_connect_uses_shared_live_terminal_ui_without_duplicate_pairing(self):
        with patch.object(wizard.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run, \
                patch.object(wizard, "invoke") as invoke:
            wizard.connect()
        run.assert_called_once_with(["/usr/lib/inithooks/bin/hubservices.py", "--relink"],
                                    stderr=subprocess.PIPE, text=True)
        invoke.assert_not_called()
        self.console.msgbox.assert_not_called()

    def test_shared_ui_cancel_returns_to_parent_without_an_error(self):
        with patch.object(wizard.subprocess, "run", return_value=subprocess.CompletedProcess([], 130)):
            wizard.connect()
        self.console.msgbox.assert_not_called()

    def test_shared_ui_reported_error_is_not_displayed_twice(self):
        with patch.object(wizard.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, stderr="")):
            wizard.connect()
        self.console.msgbox.assert_not_called()

    def test_shared_ui_failure_is_actionable_and_does_not_echo_raw_stderr(self):
        for outcome in (OSError("missing"), subprocess.CompletedProcess([], 1, stderr="Traceback private-token")):
            with patch.object(wizard.subprocess, "run") as run:
                if isinstance(outcome, OSError):
                    run.side_effect = outcome
                else:
                    run.return_value = outcome
                wizard.connect()
            message = self.console.msgbox.call_args.args[1]
            self.assertIn("try Link to Hub again", message)
            self.assertNotIn("Traceback", message)
            self.assertNotIn("private-token", message)

    def test_linked_status_refreshes_once_without_duplicate_sync(self):
        self.console.menu.return_value = ("ok", "Status")
        local = {"status": "ready", "connection_status": "linked", "mode": "hub", "host": "smtp.example"}
        with patch.object(wizard, "invoke", side_effect=[local, local]) as invoke:
            wizard.run()
        self.assertEqual(invoke.call_args_list[1].args, ("status",))
        labels = [item[0] for item in self.console.menu.call_args.args[2]]
        self.assertEqual(labels.count("Status"), 1)
        self.assertNotIn("Sync", labels)
        self.assertNotIn("Custom", labels)
        self.assertNotIn("Reset mail", labels)
        self.assertIn("Test", labels)

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
