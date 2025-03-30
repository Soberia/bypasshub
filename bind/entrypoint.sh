#!/usr/bin/env bash

trap 'exit' TERM INT

install -d -m 0755 /tmp/bind/{cache,keys}
cp /etc/bind/named.conf /tmp/bind/named.conf
cp /etc/bind/db.forward /tmp/bind/db.forward

# Configuring the firewall
sudo ip6tables -P INPUT DROP
sudo ip6tables -P FORWARD DROP
sudo ip6tables -A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
sudo ip6tables -A INPUT -i lo -j ACCEPT
sudo ip6tables -A INPUT -i eth0 -p ipv6-icmp -j ACCEPT
if [[ $ENABLE_IPV6 == true ]]; then
    source=$(
        [[ $ENABLE_AUTHORITATIVE_ZONE != true ]] &&
        echo "-s $IPV6_SUBNET" ||
        echo ''
    )
    sudo ip6tables -A INPUT -i eth0 $source -p tcp --dport 53 -j ACCEPT
    sudo ip6tables -A INPUT -i eth0 $source -p udp --dport 53 -j ACCEPT
fi

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
            sed -i "/\$$sni/,+1d" /tmp/bind/db.forward
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
        sed -i "/\$$env/d" /tmp/bind/{named.conf,db.forward}
    else
        sed -i "s|\$$env|${!env}|g" /tmp/bind/{named.conf,db.forward}
    fi
done

exec /usr/sbin/named -f -c /tmp/bind/named.conf
