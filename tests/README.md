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
