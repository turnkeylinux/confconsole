#!/bin/sh
# Compatibility entry point. Credentials are accepted only as JSON on stdin.
set -eu
set +x
case "${1:-}" in
    deconfigure) exec /usr/lib/inithooks/bin/turnkey-mail reset ;;
    --stdin) exec /usr/lib/inithooks/bin/turnkey-mail configure --stdin ;;
    *) echo 'Use turnkey-mail configure --stdin; credentials must not be passed as command arguments.' >&2; exit 2 ;;
esac
