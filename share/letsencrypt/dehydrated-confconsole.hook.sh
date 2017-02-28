#!/bin/bash

function hook_log {
    echo "INFO: ${1} ($(date "+%Y-%m-%d %H:%M:%S"))"
}

function deploy_challenge {
    local DOMAIN="${1}" TOKEN_FILENAME="${2}" TOKEN_VALUE="${3}"

    hook_log "Deploying challenge for $DOMAIN"
    hook_log "Serving $WELLKNOWN/$TOKEN_FILENAME on http://$DOMAIN/.well-known/acme-challenge/$TOKEN_FILENAME"
    su - -s /bin/bash -c "authbind $HTTP_BIN -d $HTTP_PID -l $HTTP_LOG 0.0.0.0 80 $WELLKNOWN/$TOKEN_FILENAME"
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
    cat "$KEYFILE" > /etc/ssl/private/cert.key
    cat "$FULLCHAINFILE" > /etc/ssl/private/cert.pem
    cat "$KEYFILE" >> /etc/ssl/private/cert.pem
}

function unchanged_cert {
    local DOMAIN="${1}" KEYFILE="${2}" CERTFILE="${3}" FULLCHAINFILE="${4}" CHAINFILE="${5}"

    hook_log "cert for $DOMAIN is unchanged - nothing to do"
}

HANDLER=$1; shift; $HANDLER $@
