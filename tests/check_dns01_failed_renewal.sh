#!/bin/bash
# Run only inside a disposable appliance with a successfully issued test cert.
set -euo pipefail
[[ ${DNS01_QA_DISPOSABLE:-} == 1 ]] || { echo 'Set DNS01_QA_DISPOSABLE=1 in the disposable test appliance.' >&2; exit 2; }
[[ $EUID == 0 ]] || exit 2
umask 077
fixture=$(mktemp -d)
config=/etc/dehydrated/confconsole.config
wrapper=/usr/lib/confconsole/plugins.d/Lets_Encrypt/dehydrated-wrapper
cp "$config" "$fixture/config"
cleanup() { cp "$fixture/config" "$config"; rm -rf "$fixture"; }
trap cleanup EXIT
sha256sum /usr/local/share/ca-certificates/cert.crt /etc/ssl/private/cert.key /etc/ssl/private/cert.pem > "$fixture/before"
printf '\nCA="https://127.0.0.1:9/directory"\n' >> "$config"
status=0
"$wrapper" --register --force --log-info > "$fixture/failure.log" 2>&1 || status=$?
cat "$fixture/failure.log"
[[ $status != 0 ]]
grep -q 'restoring original cert' "$fixture/failure.log"
! grep -q 'completed successfully' "$fixture/failure.log"
sha256sum /usr/local/share/ca-certificates/cert.crt /etc/ssl/private/cert.key /etc/ssl/private/cert.pem > "$fixture/after"
cmp "$fixture/before" "$fixture/after"
systemctl is-active --quiet apache2
printf 'Failed-renewal status, certificate/key preservation and recovery: PASS (exit %s)\n' "$status"
