#!/usr/bin/env bash

SERVER=
CONFPATH=

set_paths () {
    local warn=$1

    for x in nginx apache2 lighttpd; do
        [[ -e /etc/$x ]] && SERVER=$x
    done

    CONFPATH="/etc/$SERVER/conf-enabled/acme-wellknown.conf"
    INCLPATH="/etc/$SERVER/conf.d/acme-wellknown.conf"

    if [[ -e $CONFPATH && -e $INCLPATH ]]; then
        [[ $warn ]] && echo "Config files '$CONFPATH' and '$INCLPATH' exist, not overwriting."
        return 2
    elif [[ -e $CONFPATH || -e $INCLPATH ]]; then
        [[ $warn ]] && echo "Config file '$CONFPATH' exists, not overwriting."
        return 1
    else
        return 0
    fi
}

deploy_challenge () {
    local DOMAIN="${1}" TOKEN_FILENAME="${2}" TOKEN_VALUE="${3}"

    # This hook is called once for every domain that needs to be
    # validated, including any alternative names you may have listed.
    #
    # Parameters:
    # - DOMAIN
    #   The domain name (CN or subject alternative name) being
    #   validated.
    # - TOKEN_FILENAME
    #   The name of the file containing the token to be served for HTTP
    #   validation. Should be served by your web server as
    #   /.well-known/acme-challenge/${TOKEN_FILENAME}.
    # - TOKEN_VALUE
    #   The token value that needs to be served for validation. For DNS
    #   validation, this is what you want to put in the _acme-challenge
    #   TXT record. For HTTP validation it is the value that is expected
    #   be found in the $TOKEN_FILENAME file.

    if set_paths 1; then
        case $SERVER in
            nginx)
                cat << EOF >> $CONFPATH
server {
  listen 80;
  server_name $DOMAIN;

  location = /.well-known/acme-challenge/$TOKEN_FILENAME {
    alias $WELLKNOWN/$TOKEN_FILENAME;
  }
EOF
                ;;
            apache2)
                cat << EOF >> $CONFPATH
Alias /.well-known/acme-challenge/$TOKEN_FILENAME $WELLKNOWN/$TOKEN_FILENAME

<Directory $WELLKNOWN>
        Options None
        AllowOverride None

        # Apache 2.4
        <IfModule mod_authz_core.c>
                Require all granted
        </IfModule>
</Directory>
EOF
                ;;
            lighttpd)
                cat << EOF >> $CONFPATH
modules += "alias"

alias.url += (
 "/.well-known/acme-challenge/$TOKEN_FILENAME" => "$WELLKNOWN/$TOKEN_FILENAME"
)
EOF
                ;;
        esac

        touch $CONFPATH.new
        service $SERVER reload || true
    fi
}

clean_challenge () {
    local DOMAIN="${1}" TOKEN_FILENAME="${2}" TOKEN_VALUE="${3}"

    set_paths || true
    [[ -e $CONFPATH.new ]] && rm -f $CONFPATH $CONFPATH.new
}

deploy_cert () {
    local DOMAIN="${1}" KEYFILE="${2}" CERTFILE="${3}" FULLCHAINFILE="${4}" CHAINFILE="${5}" TIMESTAMP="${6}"
}

unchanged_cert () {
    local DOMAIN="${1}" KEYFILE="${2}" CERTFILE="${3}" FULLCHAINFILE="${4}" CHAINFILE="${5}"
}

HANDLER=$1; shift; $HANDLER $@

