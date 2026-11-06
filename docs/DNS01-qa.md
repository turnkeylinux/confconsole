# DNS-01 credential editor validation

Run on a disposable TurnKey guest with Python 3, python3-yaml,
python3-dialog, python3-pexpect and python3-pyte installed:

```sh
sudo python3 -m unittest discover -s tests -p 'test_dns01*.py' -v
sudo python3 tests/exercise_dns01_terminal.py
sudo python3 -m compileall -q confconsole.py plugins.d tests
```

The unit suite exercises the actual plugin loader, pristine provider templates, existing credentials,
authentication changes, malformed settings, cancellation, retry and private
atomic persistence. The terminal exercise drives the real Dialog widgets in
60x24, 80x24 and 120x24 PTYs. It verifies saving Cloudflare credentials,
secret masking and scrolling a 60-line generic configuration. At 60 and 80
columns it also exercises invalid-zone recovery, Global API key entry, Back
and cancellation for both editors. Rendered terminal
states are written under `terminal-evidence/` for inspection.

On 2026-11-06, all 17 unit cases and these terminal journeys passed on Debian
13.6. The captured layouts kept fields, guidance and Save/Back actions visible
at each size. A QA-only Debian binary build with `dpkg-buildpackage -us -uc -b`
also succeeded. This repository omits `debian/changelog`; the build fixture
provided a temporary `2.2.3+qa1` changelog and produced no published package.

No CI or pre-existing runtime test suite is declared in this checkout. Full
Ruff inspection was compared with source `0f37b487`: baseline 180 findings,
candidate 178, with no introduced diagnostic by file, code and message.
Existing lint debt remains; focused checks of the new editor and tests pass.

Anchored or aliased YAML credentials use the full editor to preserve references.
A regression covers an anchored secret referenced by another setting.

## Installed-package and ACME acceptance

A disposable PrestaShop-derived guest installed the candidate Debian package
and invoked `confconsole --plugin='get certificate'` through an actual PTY.
The wizard accepted credentials from the unmodified Cloudflare template,
issued a staging certificate and deployed it through the native wrapper.
Reopening the final installed wizard preserved the saved credentials and
certificate, and exited successfully. The actual PluginManager regression
also protects the executable-file registration contract for plugin helpers.

The provider's Zone Read permission was sufficient to discover the task zone
with Zone ID omitted. The form now labels Zone ID optional and explains when
to supply it. The test token was restricted to the task zone and QA host IP.

Native renewal without a setup-only `--provider` argument initially failed:
the saved provider was not exported to the DNS hook. Exporting it restored
staging renewal, which issued a different serial and reloaded Apache. The
EXIT trap now passes the original status to cleanup. A deliberately unreachable
CA verified nonzero exit, unchanged certificate/key bytes, service availability
and an accurate recovery message:

```sh
DNS01_QA_DISPOSABLE=1 bash tests/check_dns01_failed_renewal.sh
```

Run that destructive failure-injection check only in a disposable guest with
a test certificate. It temporarily changes the ACME endpoint and restores the
original configuration on exit.

One production-CA issuance for `qa-v19-20261106.turnkeylinux.org` succeeded.
The QA host fetched the fixture's expected content using its normal CA trust
store, with hostname verification and no insecure option. The installed
renewal toggle enabled the generated cron job, whose not-yet-due path exited
successfully without requesting another certificate. Final task TXT listing
was empty after the challenge hooks cleaned up.

Live issuance used Cloudflare. Route53 and generic-provider coverage establishes
template editing and persistence; their provider APIs were not exercised.
These checks validate the candidate package and shared certificate flow;
replacement appliance publication remains a separate delivery step.
