"""Exercise the complete renewal wrapper against isolated service fixtures."""
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import time
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / 'plugins.d/Lets_Encrypt/dehydrated-wrapper'

FIXTURE = r'''#!/usr/bin/python3
import json, os, pathlib, sys, time
root = pathlib.Path(os.environ['RENEWAL_FIXTURE'])
path = root / 'state.json'
state = json.loads(path.read_text())
command, args = pathlib.Path(sys.argv[0]).name, sys.argv[1:]
status = 0
if command == 'systemctl':
    action, name = args
    state['events'].append(action + ' ' + name)
    if name == 'add-water':
        if action == 'start':
            state['water'] = True
            status = int(os.environ.get('START_FAIL', '0'))
        elif action == 'stop':
            if os.environ.get('WAIT_FOR_CLEANUP') == '1':
                path.write_text(json.dumps(state))
                time.sleep(1)
            state['water'] = False
    elif name == 'webmin.service' and action == 'restart':
        config = root / 'etc/webmin/miniserv.conf'
        if config.is_file():
            state.setdefault('webmin_chains', []).append(
                [line for line in config.read_text().splitlines() if line.startswith('extracas=')])
        if os.environ.get('FAIL_ACTIVATION') == '1' and state['events'].count('restart webmin.service') == 1:
            if config.is_file():
                with config.open('a') as handle:
                    handle.write('session_timeout=300\n')
            status = 1
    elif name == state['server']:
        if action == 'stop':
            state['server_active'] = False
        elif action == 'restart':
            if state['water'] and os.environ['CHALLENGE'] == 'http-01':
                state['server_active'] = False
                status = 1
                print('bind: Address already in use', file=sys.stderr)
            else:
                state['server_active'] = True
elif command == 'netstat':
    if state['water'] and os.environ['CHALLENGE'] == 'http-01':
        # Type=simple can return before the HTTP listener is visible to netstat.
        server = '' if os.environ.get('RACY_START') == '1' else 'python3'
    else:
        server = state['server'] if state['server_active'] else ''
    if server:
        port = '80' if os.environ['CHALLENGE'] == 'http-01' else '443'
        print('tcp 0 0 0.0.0.0:' + port + ' 0.0.0.0:* LISTEN 1234/' + server)
elif command == 'dehydrated':
    state['events'].append('dehydrated')
    if os.environ.get('ACME_UNCHANGED') != '1':
        for name in ('TKL_CERTFILE', 'TKL_KEYFILE', 'TKL_COMBINED'):
            cert = pathlib.Path(os.environ[name])
            cert.write_text('replacement ' + name)
            cert.chmod(0o600)
            os.chown(cert, 0, 0)
    print('fixture ACME operation')
    if os.environ.get('WAIT_FOR_STOP') == '1':
        path.write_text(json.dumps(state))
        time.sleep(30)
    status = int(os.environ.get('ACME_FAIL', '0'))
elif command == 'curl':
    print('{"termsOfService": "https://example.test/terms"}')
path.write_text(json.dumps(state))
sys.exit(status)
'''


class RenewalCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='renewal-cleanup-')
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        for name in ('systemctl', 'netstat', 'dehydrated', 'curl', 'authbind'):
            path = self.bin / name
            path.write_text(FIXTURE)
            path.chmod(0o755)
        text = WRAPPER.read_text()
        for prefix in ('/etc/', '/usr/share/confconsole/', '/usr/lib/confconsole/',
                       '/usr/local/share/ca-certificates/', '/usr/lib/inithooks/',
                       '/var/log/confconsole/', '/var/run/', '/var/lib/hubdns/',
                       '/var/lib/dehydrated/', '/lib/systemd/', '/run/confconsole-acme'):
            text = text.replace(prefix, str(self.root) + prefix)
        self.wrapper = self.root / 'dehydrated-wrapper'
        self.wrapper.write_text(text)
        self.wrapper.chmod(0o755)
        self.etc = self.root / 'etc/dehydrated'
        self.etc.mkdir(parents=True)
        share = self.root / 'usr/share/confconsole/letsencrypt'
        shutil.copytree(ROOT / 'share/letsencrypt', share)
        (self.root / 'etc/cron.daily').mkdir(parents=True)
        (self.root / 'run').mkdir(parents=True)
        (self.root / 'etc/authbind/byport').mkdir(parents=True)
        (self.root / 'etc/authbind/byport/80').touch()
        self.certs = [self.root / 'usr/local/share/ca-certificates/cert.crt',
                      self.root / 'etc/ssl/private/cert.key',
                      self.root / 'etc/ssl/private/cert.pem']
        for index, path in enumerate(self.certs):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('original ' + path.name)
            path.chmod(0o644 if index == 0 else 0o400)
            os.chown(path, 1001 + index, 1004 + index)
        self.originals = self.snapshot()
        self.webmin = self.root / 'etc/webmin/miniserv.conf'
        self.hub_fqdn = self.root / 'var/lib/hubdns/fqdn'
        self.hub_chain = self.root / 'var/lib/dehydrated/certs/old.tklapp.com/chain.pem'

    def tearDown(self):
        self.temp.cleanup()

    def snapshot(self):
        return [(path.read_bytes(), stat.S_IMODE(path.stat().st_mode),
                 path.stat().st_uid, path.stat().st_gid) for path in self.certs]

    def run_wrapper(self, challenge='http-01', fail=False, race=False,
                    server='apache2', start_fail=False, water=False, umask=0o077,
                    fail_activation=False, unchanged=False):
        config = (self.root / 'usr/share/confconsole/letsencrypt/dehydrated-confconsole.config').read_text()
        config = config.replace('/etc/dehydrated', str(self.etc))
        config = config.replace('CHALLENGETYPE="http-01"', 'CHALLENGETYPE="' + challenge + '"')
        (self.etc / 'confconsole.config').write_text(config)
        state_path = self.root / 'state.json'
        state_path.write_text(json.dumps({'server': server, 'server_active': True,
                                          'water': water, 'events': []}))
        env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                   RENEWAL_FIXTURE=str(self.root), CHALLENGE=challenge,
                   RACY_START=str(int(race)), ACME_FAIL=str(int(fail)),
                   START_FAIL=str(int(start_fail)), FAIL_ACTIVATION=str(int(fail_activation)),
                   ACME_UNCHANGED=str(int(unchanged)))
        result = subprocess.run([str(self.wrapper), '--force'], env=env,
                                capture_output=True, text=True, timeout=10,
                                preexec_fn=lambda: os.umask(umask))
        return result, json.loads(state_path.read_text())

    def test_failed_http_renewal_stops_starting_helper_before_apache_restart(self):
        result, state = self.run_wrapper(fail=True, race=True)
        self.assertNotEqual(0, result.returncode)
        self.assertTrue(state['server_active'], result.stdout + result.stderr)
        self.assertFalse(state['water'])
        self.assertLess(state['events'].index('stop add-water'),
                        state['events'].index('restart apache2'))
        self.assertIn('restoring original cert', result.stdout)
        self.assertIn('dehydrated exited with a non-zero exit code', result.stderr)

    def test_failed_renewal_restores_all_contents_owners_and_modes_under_private_umask(self):
        result, state = self.run_wrapper(fail=True, umask=0o077)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(self.originals, self.snapshot())
        self.assertTrue(state['server_active'])

    def test_successful_http_renewal_restarts_services_after_helper_stops(self):
        result, state = self.run_wrapper()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertTrue(state['server_active'])
        self.assertFalse(state['water'])
        self.assertLess(state['events'].index('stop add-water'),
                        state['events'].index('restart apache2'))
        self.assertIn('restart webmin.service', state['events'])
        for path in self.certs:
            self.assertTrue(path.read_text().startswith('replacement '))
            self.assertFalse(path.with_name(path.name + '.bak').exists())

    def test_failed_helper_start_is_cleaned_up_before_services_restart(self):
        result, state = self.run_wrapper(start_fail=True, race=True)
        self.assertNotEqual(0, result.returncode)
        self.assertTrue(state['server_active'])
        self.assertFalse(state['water'])
        self.assertLess(state['events'].index('stop add-water'),
                        state['events'].index('restart apache2'))
        self.assertEqual(self.originals, self.snapshot())

    def stop_worker_at(self, event, **fixture_options):
        self.run_wrapper(fail=True)
        state_path = self.root / "state.json"
        state_path.write_text(json.dumps({"server": "apache2", "server_active": True,
                                          "water": False, "events": []}))
        runner = """
import importlib.util
import sys
spec = importlib.util.spec_from_file_location("service", sys.argv[1])
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)
with open(sys.argv[3], "a") as lock, service.cancellation_requests() as cancelled:
    try:
        service.run_wrapper([sys.argv[2], "--force"], lock.fileno(), cancelled)
    except KeyboardInterrupt:
        sys.exit(130)
"""
        env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                   RENEWAL_FIXTURE=str(self.root), CHALLENGE="http-01",
                   **fixture_options)
        with subprocess.Popen(
            [sys.executable, "-c", runner, str(WRAPPER.with_name("certificate_service.py")),
             str(self.wrapper), str(self.root / "test.lock")], env=env,
        ) as worker:
            try:
                until = time.monotonic() + 5
                while time.monotonic() < until:
                    try:
                        if event in json.loads(state_path.read_text())["events"]:
                            break
                    except ValueError:
                        pass
                    time.sleep(0.03)
                else:
                    self.fail(f"The wrapper did not reach {event} with Apache stopped")
                self.assertFalse(json.loads(state_path.read_text())["server_active"])
                worker.send_signal(signal.SIGTERM)
                self.assertEqual(130, worker.wait(timeout=5))
            finally:
                if worker.poll() is None:
                    worker.send_signal(signal.SIGTERM)
        self.assertEqual(self.originals, self.snapshot())
        state = json.loads(state_path.read_text())
        self.assertTrue(state["server_active"])
        self.assertFalse(state["water"])
        self.assertIn("restart apache2", state["events"])

    def test_stopping_python_worker_allows_wrapper_to_recover_services(self):
        self.stop_worker_at("dehydrated", WAIT_FOR_STOP="1")

    def test_cancellation_during_cleanup_preserves_service_recovery(self):
        self.stop_worker_at("stop add-water", ACME_FAIL="1", WAIT_FOR_CLEANUP="1")

    def test_initial_issuance_failure_restores_absence_of_separate_crt(self):
        self.certs[0].unlink()
        result, state = self.run_wrapper(fail=True)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(self.certs[0].exists())
        self.assertTrue(state['server_active'])

    def test_failed_activation_restores_certificate_and_restarts_services_again(self):
        result, state = self.run_wrapper(fail_activation=True)
        self.assertEqual(75, result.returncode)
        self.assertEqual(self.originals, self.snapshot())
        self.assertTrue(state['server_active'])
        self.assertEqual(2, state['events'].count('restart apache2'))
        self.assertEqual(2, state['events'].count('restart webmin.service'))

    def hub_webmin_config(self):
        self.hub_fqdn.parent.mkdir(parents=True, exist_ok=True)
        self.hub_fqdn.write_text('Old.tklapp.com.\n')
        self.webmin.parent.mkdir(parents=True, exist_ok=True)
        config = f'keyfile={self.certs[2]}\ncertfile=\nextracas={self.hub_chain}\n'
        self.webmin.write_text(config)
        return config

    def test_success_uses_new_shared_chain_before_webmin_restart(self):
        original = self.hub_webmin_config()
        self.webmin.chmod(0o640)
        result, state = self.run_wrapper()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual([[f'extracas={self.certs[2]}']], state['webmin_chains'])
        self.assertEqual(original.replace(str(self.hub_chain), str(self.certs[2])),
                         self.webmin.read_text())
        self.assertEqual(0o640, stat.S_IMODE(self.webmin.stat().st_mode))

    def test_webmin_activation_failure_restores_only_the_managed_directive(self):
        original = self.hub_webmin_config()
        result, state = self.run_wrapper(fail_activation=True)
        self.assertEqual(75, result.returncode)
        self.assertEqual([[f'extracas={self.certs[2]}'], [f'extracas={self.hub_chain}']],
                         state['webmin_chains'])
        self.assertEqual(self.originals, self.snapshot())
        self.assertEqual(original + 'session_timeout=300\n', self.webmin.read_text())

    def test_unchanged_or_failed_cert_does_not_change_webmin_chain(self):
        for options in ({'unchanged': True}, {'fail': True}):
            with self.subTest(options=options):
                original = self.hub_webmin_config()
                result, state = self.run_wrapper(**options)
                self.assertEqual(bool(options.get('fail')), result.returncode != 0)
                self.assertEqual([[f'extracas={self.hub_chain}']], state['webmin_chains'])
                self.assertEqual(original, self.webmin.read_text())

    def test_custom_or_ambiguous_webmin_settings_are_preserved(self):
        original = self.hub_webmin_config()
        for config in (
            original.replace(str(self.hub_chain), '/etc/webmin/custom-chain.pem'),
            original.replace('certfile=\n', 'certfile=/etc/webmin/custom.pem\n'),
            original.replace(str(self.certs[2]), '/etc/webmin/custom-key.pem'),
            original.replace(f'extracas={self.hub_chain}\n', ''),
            original + f'extracas={self.hub_chain}\n',
            original + ' extracas = /etc/webmin/custom-chain.pem\n',
            original + 'certfile=\n',
            original + f'keyfile={self.certs[2]}\n',
        ):
            with self.subTest(config=config):
                self.webmin.write_text(config)
                self.certs[2].write_bytes(self.originals[2][0])
                result, _ = self.run_wrapper()
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertEqual(config, self.webmin.read_text())

    def test_hostname_certificate_can_keep_using_global_webmin_chain(self):
        original = self.hub_webmin_config()
        for directive in ('ipkey_special.example=', '  ipkey_special.example = '):
            with self.subTest(directive=directive):
                config = original + directive + '/etc/webmin/special.pem\n'
                self.webmin.write_text(config)
                self.certs[2].write_bytes(self.originals[2][0])
                result, state = self.run_wrapper()
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertEqual([[f'extracas={self.hub_chain}']], state['webmin_chains'])
                self.assertEqual(config, self.webmin.read_text())

    def test_linked_settings_and_missing_hub_hostname_are_preserved(self):
        original = self.hub_webmin_config()
        target = self.webmin.with_name('custom.conf')
        self.webmin.rename(target)
        self.webmin.symlink_to(target)
        result, _ = self.run_wrapper()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertTrue(self.webmin.is_symlink())
        self.assertEqual(original, target.read_text())
        self.webmin.unlink()
        target.rename(self.webmin)
        self.hub_fqdn.unlink()
        self.certs[2].write_bytes(self.originals[2][0])
        result, _ = self.run_wrapper()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(original, self.webmin.read_text())

    def test_dns_renewal_uses_no_http_helper(self):
        result, state = self.run_wrapper(challenge='dns-01', server='nginx')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertTrue(state['server_active'])
        self.assertNotIn('start add-water', state['events'])
        self.assertNotIn('stop add-water', state['events'])
        self.assertNotIn('stop nginx', state['events'])
        self.assertIn('restart nginx', state['events'])

    def test_dns_failure_restores_files_without_stopping_an_unowned_helper(self):
        result, state = self.run_wrapper(challenge='dns-01', fail=True,
                                         server='nginx', water=True)
        self.assertNotEqual(0, result.returncode)
        self.assertTrue(state['water'])
        self.assertNotIn('stop add-water', state['events'])
        self.assertEqual(self.originals, self.snapshot())

    def test_unknown_http_listener_is_preserved(self):
        for server in ('python3', 'unknownserver'):
            with self.subTest(server=server):
                result, state = self.run_wrapper(server=server)
                self.assertNotEqual(0, result.returncode)
                self.assertTrue(state['server_active'])
                self.assertNotIn('stop ' + server, state['events'])
                self.assertNotIn('restart ' + server, state['events'])
                self.assertNotIn('start add-water', state['events'])
                self.assertNotIn('stop add-water', state['events'])
                self.assertEqual(self.originals, self.snapshot())


if __name__ == '__main__':
    unittest.main()
