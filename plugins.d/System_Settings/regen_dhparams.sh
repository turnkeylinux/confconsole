#!/bin/bash -e

# Bash script which leverages turnkey-make-ssl-cert to regen dhparams file.
#
# This file is part of the Regenerate_DHParams Confconsole plugin but is
# mostly a copy of the 15regen-sslcert inithook, adjusted to be relevant as
# a Confconsole plugin.

fatal() { echo "FATAL: $@" 1>&2 ; exit 1 ; }
info() { echo "INFO: $@" ; }

turnkey_make_ssl_cert=$(which turnkey-make-ssl-cert) \
    || fatal "turnkey-make-ssl-cert executable not found."

DH_BITS=${1}

info "regen_dhparams run with dh_bits = $DH_BITS"
$turnkey_make_ssl_cert --dh-params-only --dh-bits $DH_BITS

# Restart relevant services
SERVICES="\
    nginx
    apache2
    lighttpd
    tomcat8
    stunnel4@webmin
    stunnel4@shellinabox"

info "Restarting relevant services."
for service in $SERVICES; do
    service="${service}.service"
    if systemctl list-units --full -all | grep -Fq $service; then
        info "$service found; (re)starting..."
        if systemctl is-active --quiet $service; then
            systemctl restart --quiet $service
        else
            systemctl start --quiet $service
        fi
    fi
done
