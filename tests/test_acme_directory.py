"""The wizard must handle directory failures before changing any settings."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "get_certificate", ROOT / "plugins.d/Lets_Encrypt/get_certificate.py"
)
wizard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wizard)


class DirectoryTests(unittest.TestCase):
    def invoke(self, response=None, error=None):
        console = Mock()
        console.yesno.return_value = "cancel"
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "settings"
            original = "existing settings and credentials\n"
            config.write_text(original)
            with (
                patch.object(wizard, "console", console, create=True),
                patch.object(wizard, "d_conf_path", str(config)),
                patch.object(
                    wizard.requests,
                    "get",
                    return_value=response,
                    side_effect=error,
                ) as get,
            ):
                wizard.run()
            self.assertEqual(config.read_text(), original)
            self.assertEqual(list(Path(directory).iterdir()), [config])
        get.assert_called_once_with(wizard.LE_INFO_URL, timeout=(5, 15))
        return console

    def test_success_reaches_terms_with_verification_defaults(self):
        response = Mock()
        response.json.return_value = {
            "meta": {"termsOfService": "https://example.org/terms.pdf"}
        }
        console = self.invoke(response)
        response.raise_for_status.assert_called_once_with()
        console.msgbox.assert_not_called()
        console.yesno.assert_called_once()
        self.assertIn(
            "https://example.org/terms.pdf", console.yesno.call_args.args[0]
        )
        console.menu.assert_not_called()

    def test_network_failures_are_actionable_and_do_not_echo_exception(self):
        for error, expected in (
            (
                requests.exceptions.SSLError("private-proxy-details"),
                "TLS certificate",
            ),
            (
                requests.exceptions.ConnectTimeout("private-proxy-details"),
                "timed out",
            ),
            (
                requests.exceptions.ReadTimeout("private-proxy-details"),
                "timed out",
            ),
            (
                requests.exceptions.ConnectionError("private-proxy-details"),
                "Check DNS",
            ),
            (
                requests.exceptions.RequestException("private-proxy-details"),
                "request failed",
            ),
        ):
            with self.subTest(error=type(error).__name__):
                console = self.invoke(error=error)
                self.assertIn(expected, console.msgbox.call_args.args[1])
                self.assertIn(
                    "Get certificate", console.msgbox.call_args.args[1]
                )
                self.assertNotIn(
                    "private-proxy-details", repr(console.mock_calls)
                )
                console.yesno.assert_not_called()
                console.menu.assert_not_called()

    def test_http_error_is_handled_before_json(self):
        response = Mock()
        response.raise_for_status.side_effect = requests.exceptions.HTTPError()
        console = self.invoke(response)
        self.assertIn("HTTP error", console.msgbox.call_args.args[1])
        response.json.assert_not_called()
        console.yesno.assert_not_called()

    def test_malformed_directory_never_reaches_terms(self):
        for body in (
            None,
            [],
            1,
            {},
            {"meta": None},
            {"meta": []},
            {"meta": {}},
            {"meta": {"termsOfService": None}},
            {"meta": {"termsOfService": 7}},
            {"meta": {"termsOfService": ""}},
            {"meta": {"termsOfService": "javascript:bad"}},
            {"meta": {"termsOfService": "https://"}},
            {"meta": {"termsOfService": "https://example.org/\nInjected"}},
        ):
            with self.subTest(body=body):
                response = Mock()
                response.json.return_value = body
                console = self.invoke(response)
                self.assertIn(
                    "invalid terms", console.msgbox.call_args.args[1]
                )
                console.yesno.assert_not_called()

    def test_invalid_json_is_reported_without_response_contents(self):
        response = Mock()
        response.json.side_effect = requests.exceptions.JSONDecodeError(
            "bad", "private-response", 0
        )
        console = self.invoke(response)
        self.assertIn("invalid terms", console.msgbox.call_args.args[1])
        self.assertNotIn("private-response", repr(console.mock_calls))

    def test_user_can_retry_after_failure(self):
        console = Mock()
        console.yesno.return_value = "cancel"
        response = Mock()
        response.json.return_value = {
            "meta": {"termsOfService": "https://example.org/terms.pdf"}
        }
        with (
            patch.object(wizard, "console", console, create=True),
            patch.object(
                wizard.requests,
                "get",
                side_effect=[requests.exceptions.SSLError(), response],
            ) as get,
        ):
            wizard.run()
            wizard.run()
        self.assertEqual(get.call_count, 2)
        console.msgbox.assert_called_once()
        console.yesno.assert_called_once()


if __name__ == "__main__":
    unittest.main()
