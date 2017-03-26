#!/bin/bash -ex

fatal() { echo "fatal [$(basename $0)]: $@" 1>&2; exit 1; }
info() { echo "info [$(basename $0)]: $@"; }

usage() {
cat<<EOF
Syntax: $(basename $0) host port login password
- or -
Syntax: $(basename $0) deconfigure

(De)configure mail relaying
EOF
exit 1
}

cfgfile=/etc/postfix/main.cf
pwdfile=/etc/postfix/sasl_passwd
options=( relayhost smtp_sasl_auth_enable smtp_sasl_password_maps smtp_sasl_security_options smtp_tls_security_level header_size_limit )

configure_postfix() {
    info $FUNCNAME $@
    host=$1
    port=$2
    username=$3
    password=$4

    hostport="[$host]:$port"
    values=( $hostport yes hash:/etc/postfix/sasl_passwd noanonymous may 4096000 )

    echo >> $cfgfile
    for (( i = 0; i < ${#options[@]}; i++ )); do
        sed -i "/${options[$i]}/d; \$a${options[i]} = ${values[i]}" $cfgfile
    done

    cat << EOF > $pwdfile
$hostport $username:$password
EOF

    chown root:root $pwdfile
    chmod 600 $pwdfile

    postmap $pwdfile
    postfix reload || true
}

deconfigure_postfix() {
    [[ -e $pwdfile ]] && shred -u $pwdfile
    for var in "${options[@]}"; do
        sed -i "/${var}/d" $cfgfile
    done
}

if [[ $# < 1 || $# > 4 ]]; then
    usage
fi

if [[ $# == 1 && $1 == 'deconfigure' ]]; then
    deconfigure_postfix
else
    configure_postfix $@
fi

sleep 10

