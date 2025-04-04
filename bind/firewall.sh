#!/usr/bin/env sh

ip6tables -P INPUT DROP
ip6tables -P FORWARD DROP
ip6tables -A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
ip6tables -A INPUT -i lo -j ACCEPT
ip6tables -A INPUT -i eth0 -p ipv6-icmp -j ACCEPT
if [ "$ENABLE_IPV6" = true ]; then
    source=$(
        [ "$ENABLE_AUTHORITATIVE_ZONE" != true ] &&
        echo "-s $IPV6_SUBNET" ||
        echo ''
    )
    ip6tables -A INPUT -i eth0 $source -p tcp --dport 53 -j ACCEPT
    ip6tables -A INPUT -i eth0 $source -p udp --dport 53 -j ACCEPT
fi
