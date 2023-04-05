#!/bin/bash

# This dehydrated hook script is packaged with Confconsole.
# It is designed to be used in conjunction with the TurnKey dehydrated-wrapper.
# For more info, please see https://www.turnkeylinux.org/docs/letsencypt

export PROVIDER_UPDATE_DELAY=${PROVIDER_UPDATE_DELAY:-"30"}
#provider 'auto' can be used since roughly v3.3.13 of lexicon.
export PROVIDER=${PROVIDER:-"auto"}

function hook_log {
    default="[$(date "+%Y-%m-%d %H:%M:%S")] $(basename $0):"
    case ${1} in
        info)    echo "$default INFO: ${2}";;
        success) echo "$default SUCCESS: ${2}" >&2;;
        fatal)   echo "$default FATAL: ${2}" >&2; exit 1;;
    esac
}

for var in PROVIDER LEXICON_CONFIG_DIR TKL_KEYFILE TKL_CERTFILE TKL_COMBINED TKL_DHPARAM; do
    eval "z=\$$var"
    [ -z $z ] && hook_log fatal "$var is not set. Exiting..."
done

function deploy_challenge {
    local DOMAIN="${1}" TOKEN_FILENAME="${2}" TOKEN_VALUE="${3}"

    hook_log info "Deploying challenge for $DOMAIN."
    hook_log info "Creating a TXT challenge-record with $PROVIDER."
    lexicon --config-dir $LEXICON_CONFIG_DIR $PROVIDER create ${DOMAIN} TXT --name="_acme-challenge.${DOMAIN}." \
      --content="${TOKEN_VALUE}"

    local DELAY_COUNTDOWN=$PROVIDER_UPDATE_DELAY
    while [ $DELAY_COUNTDOWN -gt 0 ]; do
        echo -ne "${DELAY_COUNTDOWN}\033[0K\r"
        sleep 1
        : $((DELAY_COUNTDOWN--))
    done
}

function invalid_challenge() {
    local DOMAIN="${1}" RESPONSE="${2}"

    hook_log fatal "Challenge response for ${DOMAIN} failed: ${RESPONSE}."
}

function clean_challenge {
    local DOMAIN="${1}" TOKEN_FILENAME="${2}" TOKEN_VALUE="${3}"

    hook_log info "Clean challenge for ${DOMAIN}."

    lexicon --config-dir $LEXICON_CONFIG_DIR $PROVIDER delete ${DOMAIN} TXT --name="_acme-challenge.${DOMAIN}." \
    --content="${TOKEN_VALUE}"
}

function deploy_cert {
    local DOMAIN="${1}" KEYFILE="${2}" CERTFILE="${3}" FULLCHAINFILE="${4}" CHAINFILE="${5}" TIMESTAMP="${6}"

    hook_log success "Cert request successful. Writing relevant files for $DOMAIN."
    hook_log info "fullchain: $FULLCHAINFILE"
    hook_log info "keyfile: $KEYFILE"
    cat "$KEYFILE" > $TKL_KEYFILE
    cat "$FULLCHAINFILE" > $TKL_CERTFILE
    cat $TKL_CERTFILE $TKL_KEYFILE $TKL_DHPARAM  > $TKL_COMBINED
    hook_log success "Files written/created for $DOMAIN: $TKL_CERTFILE - $TKL_KEYFILE - $TKL_COMBINED."
}

function unchanged_cert {
    local DOMAIN="${1}" KEYFILE="${2}" CERTFILE="${3}" FULLCHAINFILE="${4}" CHAINFILE="${5}"

    hook_log info "cert for $DOMAIN is unchanged - nothing to do"
}

[ $(which lexicon) ] || hook_log fatal "lexicon is not installed."
if [ "$PROVIDER" = "auto" ]; then
    [ $(which nslookup) ] || hook_log fatal "nslookup is not installed(provided by dnsutils package)."
fi

HANDLER="$1"; shift
case "$HANDLER" in
    deploy_challenge)
        deploy_challenge "$@";;
    invalid_challenge)
        invalid_challenge "$@";;
    clean_challenge)
        clean_challenge "$@";;
    deploy_cert)
        deploy_cert "$@";;
    unchanged_cert)
        unchanged_cert "$@";;
esac
