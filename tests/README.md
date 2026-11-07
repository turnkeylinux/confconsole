# Networking regression tests

Run on a system with Confconsole's Debian dependencies installed:

```sh
python3 -m unittest discover -s tests -v
```

These tests replace interface operations and the dialog transport. They check
IPv6 resolver validation, retained edits, cancellation, terminal width, and
propagation of a failed static apply even when an address already exists.

For release acceptance, also exercise the actual dialog and network stack in
an isolated VM. Enter and retain IPv6 resolvers at 60, 80 and 120 columns,
correct invalid input, cancel, and retry an apply failure. Verify the resulting
resolver records and a DNS query over IPv6, then reboot and repeat the query.
Record whether IPv6 addresses came from SLAAC or DHCPv6, and identify any local
DNS fixture separately from public IPv6 connectivity.

# ACME directory checks

The full suite also verifies directory TLS, timeout, connection, HTTP and JSON
failures before settings can change, plus a successful retry into the terms
prompt. It asserts explicit connect/read timeouts and one request per attempt.

For installed-entrypoint checks, use a disposable guest with the candidate
package installed. `acme_directory_proxy.py` is a loopback-only CONNECT fixture.
It expects a short-lived certificate and key for
`acme-v02.api.letsencrypt.org` under `/root/acme-directory-qa/`, plus its `mode`
file. Generate that fixture certificate with a matching DNS subjectAltName,
then start the proxy inside the guest. Keep its private key in the fixture.

Run `exercise_acme_directory.py` on the Docker controller with pexpect and pyte
installed and `ACME_QA_CONTAINER` set to that disposable container. The driver
uses the ordinary installed `confconsole --plugin='get certificate'` command.
It first verifies rejection of the untrusted test certificate, then supplies
the test CA through the process-local `REQUESTS_CA_BUNDLE` for a successful
retry. HTTP errors and malformed responses are delivered over that verified
fixture connection. The host's trust store remains unchanged.

Inspect `acme-terminal-evidence/` for the 60, 80 and 120-column states. Success
stops at declining the terms prompt, so these checks request no certificates.
Stop the proxy and remove its certificate/key directory after testing.

# App email

The full suite covers Hub pairing, cancellation, expired and denied approval,
masked custom SMTP credentials and delegation to the shared inithooks helper.
The helper owns Postfix and credential writes; the console supplies JSON through
stdin, without passwords in command arguments.

Run `python3 tests/exercise_mail_terminal.py EVIDENCE_DIRECTORY` in an isolated
Debian environment with pexpect and pyte. It uses real dialog widgets with
fixture service responses at 60, 80 and 120 columns, covering disconnected and
connected menus, browser approval, pending, expired, denied, unavailable and
success states, and custom SMTP password masking. The portable capture uses a
Linux terminal and ASCII borders. Inspect the captured screens as well as the
functional assertions. The fixture sends no email and changes no services.
