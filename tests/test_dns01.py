import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "plugins.d/Lets_Encrypt" / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


config = load("dns_config")
dns = load("dns_01")
wizard = load("get_certificate")


class ProviderTests(unittest.TestCase):
    def test_real_plugin_loader_registers_editor(self):
        spec = importlib.util.spec_from_file_location(
            "plugin", ROOT / "plugin.py"
        )
        plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin)
        with tempfile.TemporaryDirectory() as directory:
            shutil.copytree(
                ROOT / "plugins.d/Lets_Encrypt",
                Path(directory) / "Lets_Encrypt",
            )
            manager = plugin.PluginManager(directory, {"console": Mock()})
            editor = manager.impByPath("Lets_Encrypt/dns_config.py")
            loaded_wizard = manager.impByPath(
                "Lets_Encrypt/get_certificate.py"
            )
            self.assertIs(loaded_wizard.dns_config, editor)
            self.assertTrue(callable(editor.edit_config))

    def test_templates_load_without_creating_files(self):
        with (
            tempfile.TemporaryDirectory() as path,
            patch.multiple(
                dns,
                LEXICON_CONF_DIR=path,
                LEXICON_SHARE_DIR=str(ROOT / "share/letsencrypt"),
            ),
        ):
            for provider in ("cloudflare", "route53", "other"):
                target, lines = dns.load_config(provider)
                self.assertGreater(len(lines), 12)
                self.assertFalse(Path(target).exists())
                self.assertEqual(config.parse_config("\n".join(lines)), {})

    def test_cloudflare_keeps_other_options_and_comments(self):
        text = (
            "# keep\nauth_token: old # note\nzone_id: old\n"
            "ttl: 120\ncustom:\n  values: [a, b]\n"
        )
        actual = config.update_cloudflare(
            text,
            {
                "auth_token": 'new: # "secret"',
                "zone_id": "",
                "auth_username": "user@example.com",
            },
        )
        parsed = config.parse_config(actual)
        self.assertEqual(parsed["auth_token"], 'new: # "secret"')
        self.assertNotIn("zone_id", parsed)
        self.assertIn("# note", actual)
        self.assertIn("# keep", actual)
        self.assertIn("custom:\n  values: [a, b]\n", actual)
        self.assertEqual(parsed["ttl"], 120)

    def test_template_becomes_usable_without_deleting_instructions(self):
        template = (
            ROOT / "share/letsencrypt/"
            "lexicon-confconsole-provider_cloudflare.yml"
        ).read_text()
        result = config.update_cloudflare(
            template,
            {
                "auth_token": "scoped-secret",
                "zone_id": "a" * 32,
                "auth_username": "",
            },
        )
        self.assertTrue(result.startswith(template))
        self.assertEqual(config.parse_config(result)["zone_id"], "a" * 32)

    def test_existing_global_key_switch_removes_email(self):
        actual = config.update_cloudflare(
            "auth_username: user@example.com\nauth_token: old\n",
            {"auth_username": "", "auth_token": "new", "zone_id": ""},
        )
        self.assertEqual(config.parse_config(actual), {"auth_token": "new"})

    def test_complex_credentials_require_full_editor(self):
        for text in (
            "auth_token: |\n  secret\n",
            "{auth_token: secret}",
            "defaults: &base {auth_token: secret}\n<<: *base\n",
            "secret: &s value\nauth_token: *s\n",
        ):
            with (
                self.subTest(text=text),
                self.assertRaises(config.ConfigError),
            ):
                config.cloudflare_values(text)

    def test_anchored_credential_uses_full_editor(self):
        text = "auth_token: &credential old\nother_option: *credential\n"
        console = Mock()
        console.editbox.return_value = ("ok", text)
        self.assertEqual(config.edit_cloudflare(console, text), text)
        console._wrapper.assert_not_called()
        self.assertEqual(config.parse_config(text)["other_option"], "old")

    def test_invalid_yaml_does_not_expose_secret_in_error(self):
        for text in (
            "auth_token: [SECRET",
            "- SECRET",
            "auth_token: SECRET\nauth_token: SECOND\n",
        ):
            with (
                self.subTest(text=text),
                self.assertRaises(config.ConfigError) as error,
            ):
                config.parse_config(text)
            self.assertNotIn("SECRET", str(error.exception))

    def test_new_and_existing_save_is_private_and_preserves_blanks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "provider.yml"
            for original in (None, "old"):
                if original is not None:
                    path.write_text(original)
                    path.chmod(0o644)
                # UID assertion is covered by running this test as root on QA.
                dns.save_config(str(path), ["# comment", "", "token: private"])
                self.assertEqual(
                    path.read_text(), "# comment\n\ntoken: private\n"
                )
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(path.stat().st_uid, 0)

    def test_failed_save_preserves_original_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "provider.yml"
            path.write_text("old")
            with (
                patch.object(dns, "replace", side_effect=OSError),
                self.assertRaises(OSError),
            ):
                dns.save_config(str(path), ["new"])
            self.assertEqual(path.read_text(), "old")
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_cancel_does_not_save_or_change_challenge(self):
        console = Mock()
        console.yesno.return_value = "ok"
        console.menu.return_value = ("ok", "dns-01")
        dns_mock = Mock(LEXICON_CONF_DIR="/fixture")
        dns_mock.get_providers.return_value = (
            [("cloudflare", "Cloudflare")],
            None,
        )
        dns_mock.load_config.return_value = (
            "/fixture/lexicon_cloudflare.yml",
            [],
        )
        editor = Mock()
        editor.edit_config.return_value = None
        with (
            patch.multiple(
                wizard,
                console=console,
                dns_01=dns_mock,
                dns_config=editor,
                create=True,
            ),
            patch.object(wizard, "isdir", return_value=True),
            patch.object(wizard, "glob", return_value=[]),
            patch.object(wizard.requests, "get") as get,
            patch.object(wizard, "initial_load_conf") as initial,
        ):
            get.return_value.json.return_value = {
                "meta": {"termsOfService": "test"}
            }
            console.menu.side_effect = [("ok", "dns-01"), ("ok", "cloudflare")]
            wizard.run()
            dns_mock.save_config.assert_not_called()
            initial.assert_not_called()

    def test_cloudflare_token_form_masks_secret_and_keeps_existing(self):
        console = Mock()
        console._wrapper.side_effect = [
            ("ok", "token"),
            ("ok", ["", "a" * 32]),
        ]
        actual = config.edit_cloudflare(console, "auth_token: saved-secret\n")
        self.assertEqual(
            config.parse_config(actual)["auth_token"], "saved-secret"
        )
        form_args = console._wrapper.call_args_list[1].args
        self.assertEqual(form_args[2][0][-1], 1)
        self.assertEqual(form_args[2][0][3], "")
        self.assertNotIn("saved-secret", repr(console.mock_calls))

    def test_switching_method_requires_new_secret(self):
        console = Mock()
        console._wrapper.side_effect = [
            ("ok", "key"),
            ("ok", ["", "user@example.com", ""]),
            ("ok", ["new-key", "user@example.com", ""]),
        ]
        actual = config.edit_cloudflare(console, "auth_token: old-token\n")
        self.assertEqual(config.parse_config(actual)["auth_token"], "new-key")
        console.msgbox.assert_called_once()

    def test_bad_zone_can_be_corrected(self):
        console = Mock()
        console._wrapper.side_effect = [
            ("ok", "token"),
            ("ok", ["secret", "bad"]),
            ("ok", ["", "b" * 32]),
        ]
        self.assertEqual(
            config.parse_config(config.edit_cloudflare(console, ""))[
                "zone_id"
            ],
            "b" * 32,
        )
        console.msgbox.assert_called_once()

    def test_generic_editor_preserves_long_configuration(self):
        text = "\n".join(f"key{i}: value{i}" for i in range(60)) + "\n"
        console = Mock()
        console.editbox.return_value = ("ok", text)
        self.assertEqual(config.edit_yaml(console, "route53", text), text)
        console.editbox.assert_called_once_with(
            "route53 settings (YAML)", text
        )

    def test_generic_editor_retries_invalid_input_and_cancels(self):
        console = Mock()
        console.editbox.side_effect = [
            ("ok", "token: [SECRET"),
            ("cancel", ""),
        ]
        self.assertIsNone(config.edit_yaml(console, "other", "# template"))
        self.assertNotIn("SECRET", repr(console.msgbox.mock_calls))

    def test_prerequisite_cancel_stops_setup(self):
        with (
            patch.object(dns, "exists", return_value=False),
            patch.object(dns, "console", create=True) as console,
            patch.object(dns, "run_command") as command,
        ):
            console.yesno.return_value = "cancel"
            self.assertFalse(dns.initial_setup())
            command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
