"""Exercise the complete renewal wrapper against isolated service fixtures."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / 'plugins.d/Lets_Encrypt/dehydrated-wrapper'

FIXTURE = r'''#!/usr/bin/python3
import json, os, pathlib, sys
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
            state['water'] = False
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
    for name in ('TKL_CERTFILE', 'TKL_KEYFILE', 'TKL_COMBINED'):
        cert = pathlib.Path(os.environ[name])
        cert.write_text('replacement ' + name)
        cert.chmod(0o600)
        os.chown(cert, 0, 0)
    print('fixture ACME operation')
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
                       '/var/log/confconsole/', '/var/run/', '/lib/systemd/'):
            text = text.replace(prefix, str(self.root) + prefix)
        self.wrapper = self.root / 'dehydrated-wrapper'
        self.wrapper.write_text(text)
        self.wrapper.chmod(0o755)
        self.etc = self.root / 'etc/dehydrated'
        self.etc.mkdir(parents=True)
        share = self.root / 'usr/share/confconsole/letsencrypt'
        shutil.copytree(ROOT / 'share/letsencrypt', share)
        (self.root / 'etc/cron.daily').mkdir(parents=True)
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

    def tearDown(self):
        self.temp.cleanup()

    def snapshot(self):
        return [(path.read_bytes(), stat.S_IMODE(path.stat().st_mode),
                 path.stat().st_uid, path.stat().st_gid) for path in self.certs]

    def run_wrapper(self, challenge='http-01', fail=False, race=False,
                    server='apache2', start_fail=False, water=False, umask=0o077):
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
                   START_FAIL=str(int(start_fail)))
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
