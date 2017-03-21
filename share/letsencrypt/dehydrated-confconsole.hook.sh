#!/bin/bash

# This dehydrated hook script is packaged with Confconsole.
# It is designed to be used in conjunction with the TurnKey dehydrated-wrapper.
# For more info, please see https://www.turnkeylinux.org/docs/letsencypt

function hook_info {
    echo "INFO: ${1} ($(date "+%Y-%m-%d %H:%M:%S"))"
}

function hook_warning {
    echo "WARNING: ${1} ($(date "+%Y-%m-%d %H:%M:%S"))" 2>&1
}

function deploy_challenge {
    local DOMAIN="${1}" TOKEN_FILENAME="${2}" TOKEN_VALUE="${3}"

    hook_info "Deploying challenge for $DOMAIN"
    hook_info "Serving $WELLKNOWN/$TOKEN_FILENAME on http://$DOMAIN/.well-known/acme-challenge/$TOKEN_FILENAME"
    su - -s /bin/bash -c "authbind $HTTP_BIN -d $HTTP_PID -l $HTTP_LOG $WELLKNOWN/$TOKEN_FILENAME"
}

function clean_challenge {
    local DOMAIN="${1}" TOKEN_FILENAME="${2}" TOKEN_VALUE="${3}"

    hook_info "Stopping $HTTP daemon"
    kill -9 $(cat $HTTP_PID)
    rm $HTTP_PID
}

function deploy_cert {
    local DOMAIN="${1}" KEYFILE="${2}" CERTFILE="${3}" FULLCHAINFILE="${4}" CHAINFILE="${5}" TIMESTAMP="${6}"

    hook_warning "writing cert.pem & cert.key for $DOMAIN to /etc/ssl/private"
    hook_info "fullchain: $FULLCHAIN"
    hook_info "keyfile: $KEYFILE"
    cat "$KEYFILE" > $TKL_KEYFILE
    cat "$FULLCHAINFILE" > $TKL_CERTFILE
    cat "$KEYFILE" >> $TKL_CERTFILE
}

function unchanged_cert {
    local DOMAIN="${1}" KEYFILE="${2}" CERTFILE="${3}" FULLCHAINFILE="${4}" CHAINFILE="${5}"

    hook_info "cert for $DOMAIN is unchanged - nothing to do"
}

HANDLER=$1; shift; $HANDLER $@
