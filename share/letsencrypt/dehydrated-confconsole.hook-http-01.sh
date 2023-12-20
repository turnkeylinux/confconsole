#!/bin/bash -e

# This dehydrated hook script is packaged with Confconsole.
# It is designed to be used in conjunction with the TurnKey dehydrated-wrapper.
# For more info, please see https://www.turnkeylinux.org/docs/letsencypt

# HTTP-01 Hook Script

function hook_log {
    default="[$(date "+%F %T")] $(basename "$0"):"
    case ${1} in
        info)    echo "$default INFO: ${2}";;
        success) echo "$default SUCCESS: ${2}" >&2;;
        fatal)   echo "$default FATAL: ${2}" >&2; exit 1;;
    esac
}

for var in HTTP HTTP_BIN HTTP_PID HTTP_LOG TKL_KEYFILE TKL_CERTFILE TKL_COMBINED TKL_DHPARAM; do
    eval "z=\$$var"
    [[ -z "$z" ]] && hook_log fatal "$var is not set. Exiting..."
done

function deploy_challenge {
    local DOMAIN="${1}" TOKEN_FILENAME="${2}" TOKEN_VALUE="${3}"

    hook_log info "Deploying challenge for $DOMAIN"
    hook_log info "Serving $WELLKNOWN/$TOKEN_FILENAME on http://$DOMAIN/.well-known/acme-challenge/$TOKEN_FILENAME"
    $HTTP_BIN --deploy "$WELLKNOWN/$TOKEN_FILENAME"
}

function clean_challenge {
    local DOMAIN="${1}" TOKEN_FILENAME="${2}" TOKEN_VALUE="${3}"

    hook_log info "Clean challenge for $DOMAIN"
    $HTTP_BIN --clean "$WELLKNOWN/$TOKEN_FILENAME"
}

function deploy_cert {
    local DOMAIN="${1}" KEYFILE="${2}" CERTFILE="${3}" FULLCHAINFILE="${4}" CHAINFILE="${5}" TIMESTAMP="${6}"

    hook_log success "Cert request successful. Writing relevant files for $DOMAIN."
    hook_log info "fullchain: $FULLCHAINFILE"
    hook_log info "keyfile: $KEYFILE"
    cat "$KEYFILE" > "$TKL_KEYFILE"
    cat "$FULLCHAINFILE" > "$TKL_CERTFILE"
    cat "$TKL_CERTFILE" "$TKL_KEYFILE" "$TKL_DHPARAM"  > "$TKL_COMBINED"
    hook_log success "Files written/created for $DOMAIN: $TKL_CERTFILE - $TKL_KEYFILE - $TKL_COMBINED."
}

function unchanged_cert {
    local DOMAIN="${1}" KEYFILE="${2}" CERTFILE="${3}" FULLCHAINFILE="${4}" CHAINFILE="${5}"

    hook_log info "cert for $DOMAIN is unchanged - nothing to do"
}

HANDLER="$1"; shift
case "$HANDLER" in
    deploy_challenge)
        deploy_challenge "$@";;
    clean_challenge)
        clean_challenge "$@";;
    deploy_cert)
        deploy_cert "$@";;
    unchanged_cert)
        unchanged_cert "$@";;
esac
