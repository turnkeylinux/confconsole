#!/bin/bash

# This dehydrated hook script is packaged with Confconsole.
# It is designed to be used in conjunction with the TurnKey dehydrated-wrapper.
# For more info, please see https://www.turnkeylinux.org/docs/letsencypt

function hook_log {
    echo "INFO: ${1} ($(date "+%Y-%m-%d %H:%M:%S"))"
}

function deploy_challenge {
    local DOMAIN="${1}" TOKEN_FILENAME="${2}" TOKEN_VALUE="${3}"

    hook_log "Deploying challenge for $DOMAIN"
    hook_log "Serving $WELLKNOWN/$TOKEN_FILENAME on http://$DOMAIN/.well-known/acme-challenge/$TOKEN_FILENAME"
    su - -s /bin/bash -c "authbind $HTTP_BIN -d $HTTP_PID -l $HTTP_LOG $WELLKNOWN/$TOKEN_FILENAME"
}

function clean_challenge {
    local DOMAIN="${1}" TOKEN_FILENAME="${2}" TOKEN_VALUE="${3}"

    hook_log "Stopping $HTTP daemon"
    kill -9 $(cat $HTTP_PID)
    rm $HTTP_PID
}

function deploy_cert {
    local DOMAIN="${1}" KEYFILE="${2}" CERTFILE="${3}" FULLCHAINFILE="${4}" CHAINFILE="${5}" TIMESTAMP="${6}"

    hook_log "writing cert.pem & cert.key for $DOMAIN to /etc/ssl/private"
    hook_log "fullchain: $FULLCHAIN"
    hook_log "keyfile: $KEYFILE"
    cat "$KEYFILE" > $TKL_KEYFILE
    cat "$FULLCHAINFILE" > $TKL_CERTFILE
    cat "$KEYFILE" >> $TKL_CERTFILE
    export CERTS_DONE=1
}

function unchanged_cert {
    local DOMAIN="${1}" KEYFILE="${2}" CERTFILE="${3}" FULLCHAINFILE="${4}" CHAINFILE="${5}"

    hook_log "cert for $DOMAIN is unchanged - nothing to do"
    export CERTS_DONE=1
}

HANDLER=$1; shift; $HANDLER $@
