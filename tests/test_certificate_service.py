"""Exercise Confconsole certificate state, including the browser worker."""

import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins.d/Lets_Encrypt/certificate_service.py"
SPEC = importlib.util.spec_from_file_location("certificate_service", SCRIPT)
service = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(service)


class CertificateServiceTests(unittest.TestCase):
    def setUp(self):
        temp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(temp)
        self.folder = self.root / "dehydrated"
        self.folder.mkdir()
        self.run_folder = self.root / "run"
        self.run_folder.mkdir(mode=0o700)
        self.lexicon = self.root / "lexicon"
        self.lexicon.touch()
        self.cert = self.root / "cert.pem"
        self.cron = self.root / "cron"
        self.archive = self.root / "archive"
        self.enterContext(patch.multiple(
            service, ETC=self.folder, RUN=self.run_folder, LEXICON=self.lexicon,
            LOCK=self.root / "lock", CERT=self.cert, CERT_KEY=self.root / "key.pem",
            CERT_CHAIN=self.root / "chain.crt", CRON=self.cron, ARCHIVE=self.archive,
            SHARE=ROOT / "share/letsencrypt",
        ))
        self.enterContext(patch.object(service, "ready", return_value=True))
        self.http = {"domains": ["EXAMPLE.COM", "www.example.com"],
                     "challenge": "http-01", "accept_terms": True}
        self.dns = {"domains": ["*.example.com"], "challenge": "dns-01",
                    "provider": "cloudflare", "credentials": {"auth_token": "private-token"},
                    "accept_terms": True}

    def test_invalid_inputs_leave_settings_and_job_untouched(self):
        for form in (dict(self.http, accept_terms=False),
                     dict(self.http, domains=["*.example.com"]),
                     dict(self.http, domains=["a.example.com; rm"]),
                     dict(self.dns, provider="../../notallowed")):
            with self.subTest(form=form), self.assertRaises(service.CertificateError):
                service.queue(form)
        self.assertEqual(list(self.folder.iterdir()), [])
        self.assertEqual(list(self.run_folder.iterdir()), [])

    def test_dns_worker_runs_install_with_private_settings_and_status(self):
        with (patch.object(service, "command", return_value=0) as command,
              patch.object(service, "run_wrapper", return_value=0) as wrapper):
            service.queue(self.dns)
            self.assertEqual((self.run_folder / "request.json").stat().st_mode & 0o777, 0o600)
            self.assertEqual("running", service.job_status()["state"])
            service.execute_job()
        launch = command.call_args_list[0].args[0]
        self.assertIn("--collect", launch)
        self.assertIn("--property=KillMode=mixed", launch)
        self.assertIn("--property=TimeoutStopSec=100s", launch)
        self.assertEqual(launch[-1], "worker")
        self.assertNotIn("private-token", repr(command.call_args_list))
        self.assertNotIn("private-token", repr(wrapper.call_args_list))
        self.assertFalse((self.run_folder / "request.json").exists())
        self.assertEqual(service.provider_file("cloudflare").stat().st_mode & 0o777, 0o600)
        self.assertIn("private-token", service.provider_file("cloudflare").read_text())
        self.assertIn(" > star_example_com", service.domains_file().read_text())
        self.assertEqual(service.job_status()["state"], "succeeded")
        self.assertNotIn("private-token", json.dumps(service.status()))
        self.assertIsNone(service.credentials_for_browser("cloudflare", {}))

    def test_failed_dns_replacement_restores_settings_and_permissions(self):
        service.config_file().write_text((service.SHARE / "dehydrated-confconsole.config").read_text())
        service.domains_file().write_text("example.com\n")
        provider = service.provider_file("cloudflare")
        provider.write_text("auth_token: previous\n")
        provider.chmod(0o600)
        installed = [service.config_file(), service.domains_file(), provider]
        prior = {path: (path.read_bytes(), path.stat().st_mode & 0o777) for path in installed}

        def fail_operation(args, lock_fd, stop_requested):
            self.assertIn("--check-installed", args)
            self.assertIn("private-token", provider.read_text())
            self.cron.write_text("changed by wrapper")
            service.hook_file().write_text("changed by wrapper")
            return 1

        with patch.object(service, "run_wrapper", side_effect=fail_operation):
            with self.assertRaisesRegex(service.CertificateError, "Check the DNS provider"):
                service.issue(self.dns)
        for path, (content, mode) in prior.items():
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(path.stat().st_mode & 0o777, mode)
        self.assertFalse(self.cron.exists())
        self.assertFalse(service.hook_file().exists())

    def test_service_restart_failure_has_actionable_message(self):
        for code, message in (
            (75, "Could not activate the certificate"),
            (76, "Could not recover a web service"),
        ):
            with self.subTest(code=code):
                with patch.object(service, "run_wrapper", return_value=code):
                    with self.assertRaisesRegex(service.CertificateError, message):
                        service.issue(self.http)
                self.assertFalse(service.domains_file().exists())

    def test_existing_custom_configuration_is_read_only_in_webmin(self):
        for path, custom in ((service.domains_file(), "one.example.com\ntwo.example.com\n"),
                             (service.domains_file(), "one.example.com > custom\n"),
                             (service.hook_file(), "# custom hook"),
                             (service.config_file(), "CA=https://custom.example.com\n"),
                             (self.cron, "custom schedule")):
            with self.subTest(path=path, custom=custom):
                path.write_text(custom)
                self.assertFalse(service.status()["configurable"])
                with self.assertRaisesRegex(service.CertificateError, "custom"):
                    service.queue(self.http)
                self.assertEqual(path.read_text(), custom)
                path.unlink()

    def test_certificate_outputs_reject_custom_links_and_nonregular_files(self):
        native = self.root / "native-webmin.pem"
        native.write_text("untouched")
        for output in (service.CERT, service.CERT_KEY, service.CERT_CHAIN):
            with self.subTest(output=output):
                output.symlink_to(native)
                self.assertFalse(service.status()["configurable"])
                with self.assertRaisesRegex(service.CertificateError, "custom"):
                    service.queue(self.http)
                self.assertTrue(output.is_symlink())
                self.assertEqual(native.read_text(), "untouched")
                output.unlink()
                output.mkdir()
                self.assertFalse(service.status()["configurable"])
                output.rmdir()
        self.assertTrue(service.status()["configurable"])

    def test_status_never_opens_a_certificate_fifo(self):
        os.mkfifo(service.CERT)
        with patch.object(service.subprocess, "run") as openssl:
            status = service.status()
        openssl.assert_not_called()
        self.assertEqual(status["domains"], [])
        self.assertFalse(status["configurable"])

    def test_worker_rechecks_output_paths_after_queuing(self):
        with patch.object(service, "command", return_value=0):
            service.queue(self.http)
        native = self.root / "native-webmin.pem"
        native.write_text("untouched")
        service.CERT.symlink_to(native)
        with patch.object(service, "run_wrapper") as wrapper:
            service.execute_job()
        wrapper.assert_not_called()
        self.assertEqual(service.job_status()["state"], "failed")
        self.assertTrue(service.CERT.is_symlink())
        self.assertEqual(native.read_text(), "untouched")
        self.assertFalse(service.domains_file().exists())

    def test_certificate_names_renewal_and_managed_state_are_real(self):
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
             "-keyout", str(self.root / "key"), "-out", str(self.cert),
             "-days", "1", "-subj", "/CN=example.com",
             "-addext", "subjectAltName=DNS:example.com,DNS:www.example.com"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        service.domains_file().write_text("example.com www.example.com\n")
        self.cron.write_bytes((service.SHARE / "dehydrated-confconsole.cron").read_bytes())
        self.cron.chmod(0o644)
        self.assertFalse(service.status()["managed"])
        with self.assertRaisesRegex(service.CertificateError, "valid TurnKey certificate"):
            service.set_renewal(True)
        account = self.archive / "example.com"
        account.mkdir(parents=True)
        (account / "cert-previous.pem").write_bytes(self.cert.read_bytes())
        result = service.status()
        self.assertEqual(result["domains"], ["example.com", "www.example.com"])
        self.assertTrue(result["expires"].endswith("+00:00"))
        self.assertTrue(result["managed"])
        self.assertTrue(result["renewal_available"])
        self.assertTrue(service.check_active_certificate())
        service.set_renewal(True)
        self.assertTrue(service.status()["renewal_enabled"])
        service.set_renewal(False)
        self.assertFalse(service.status()["renewal_enabled"])
        service.domains_file().write_text("different.example.com\n")
        self.assertFalse(service.check_active_certificate())

    def test_concurrent_issuance_and_renewal_are_rejected(self):
        with service.LOCK.open("a") as external:
            fcntl.flock(external, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for attempt in (lambda: service.queue(self.http),
                            lambda: service.set_renewal(False)):
                with self.subTest(attempt=attempt), self.assertRaisesRegex(
                    service.CertificateError, "already running"
                ):
                    attempt()
