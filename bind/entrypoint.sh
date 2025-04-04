#!/usr/bin/env bash

trap 'exit' TERM INT

install -d -g users -m 0750 /tmp/bind
install -d -m 0750 /tmp/bind/{cache,keys}
cp /etc/bind/named.conf /tmp/bind/named.conf
cp /etc/bind/db.forward /tmp/bind/db.forward

if [ ! -f /tmp/bind/domain ]; then
    echo $DOMAIN > /tmp/bind/domain
elif [[ $(< /tmp/bind/domain) != $DOMAIN ]]; then
    # The domain has been changed.
    # Removing previously generated signed zones.
    rm /tmp/bind/db.forward.* /tmp/bind/keys/* &>/dev/null
    echo $DOMAIN > /tmp/bind/domain
fi

if [[ $ENABLE_AUTHORITATIVE_ZONE == true ]]; then
    # Removing records for disabled profiles or invalid
    # SNIs which is not part of the parent domain
    for profile in 'xray' 'ocserv'; do
        sni="${profile^^}_SNI"
        if [[ $COMPOSE_PROFILES != *"$profile"* || ! ${!sni} =~ "$DOMAIN"$ ]]; then
            sed -i "/\$$sni\b/,+1d" /tmp/bind/db.forward
        fi
    done

    if [[ $ENABLE_DNSSEC != true ]]; then
        # Disabling DNSSEC signing
        sed -i "/#? dnssec/d" /tmp/bind/named.conf
    fi
else
    # Disabling authoritative mode
    sed -i "/#! authoritative/,/^}/d" /tmp/bind/named.conf
fi

# Injecting the environment variables
declare -a envs=(
    'DOMAIN'
    'XRAY_SNI'
    'OCSERV_SNI'
    'DNS_CACHE_SIZE'
    'DNS_IPV4'
    'DNS_IPV6'
    'PUBLIC_IPV4'
    'IPV6_SUBNET'
    'BIND_IPV6'
    'NGINX_IPV6'
)
for env in "${envs[@]}"; do
    if [[ $env == *"IPV6"* && ( $ENABLE_IPV6 != true || -z ${!env} ) ]]; then
        sed -i "/\$$env\b/d" /tmp/bind/{named.conf,db.forward}
    else
        sed -i "s|\$$env|${!env}|g" /tmp/bind/{named.conf,db.forward}
    fi
done

exec /usr/sbin/named -f -c /tmp/bind/named.conf
