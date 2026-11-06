# DNS-01 credential editor validation

Run on a disposable TurnKey guest with Python 3, python3-yaml,
python3-dialog, python3-pexpect and python3-pyte installed:

```sh
sudo python3 -m unittest discover -s tests -p 'test_dns01*.py' -v
sudo python3 tests/exercise_dns01_terminal.py
sudo python3 -m compileall -q confconsole.py plugins.d tests
```

The unit suite exercises pristine provider templates, existing credentials,
authentication changes, malformed settings, cancellation, retry and private
atomic persistence. The terminal exercise drives the real Dialog widgets in
60x24, 80x24 and 120x24 PTYs. It verifies saving Cloudflare credentials,
secret masking and scrolling a 60-line generic configuration. Rendered terminal
states are written under `terminal-evidence/` for inspection.

On 2026-11-06, all 15 unit cases and these terminal journeys passed on Debian
13.6. The captured layouts kept fields, guidance and Save/Back actions visible
at each size. A QA-only Debian binary build with `dpkg-buildpackage -us -uc -b`
also succeeded. This repository omits `debian/changelog`; the build fixture
provided a temporary `2.2.3+qa1` changelog and produced no published package.

No CI or pre-existing runtime test suite is declared in this checkout. Full
Ruff inspection was compared with source `0f37b487`: baseline 180 findings,
candidate 178, with no introduced diagnostic by file, code and message.
Existing lint debt remains; focused checks of the new editor and tests pass.

Certificate issuance, service deployment, renewal and a trusted browser
connection still need the separate ACME acceptance journey on a task-owned
domain. These editor tests establish credential entry and persistence, not
successful certificate deployment.
