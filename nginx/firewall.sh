#!/usr/bin/env bash

ip6tables -P INPUT DROP
ip6tables -P FORWARD DROP
ip6tables -A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
ip6tables -A INPUT -i lo -j ACCEPT
ip6tables -A INPUT -i eth0 -p ipv6-icmp -j ACCEPT
ip6tables -A INPUT -i eth0 -p tcp --dport $TLS_PORT -j ACCEPT
if [[ $COMPOSE_PROFILES == *"ocserv"* ]]; then
    ip6tables -A INPUT -i eth0 -p udp --dport $OCSERV_DTLS_PORT -j ACCEPT
fi
if [[ $COMPOSE_PROFILES == *"hysteria"* ]]; then
    ip6tables -A INPUT -i eth0 -p udp --dport $HYSTERIA_QUIC_PORT -j ACCEPT
fi
if [[ $ENABLE_IPV6 == true ]]; then
    ip6tables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
    ip6tables -A FORWARD -d $IPV6_SUBNET -j ACCEPT
fi

if [[ $ENABLE_CERTBOT_HTTP_MODE == true ]]; then
    # Redirecting the traffic to the `Certbot` container.
    # It's not possible to forward the traffic from the `NGINX`
    # process itself to the `Certbot` container because the TLS
    # certificate probably is not generated just yet and the
    # `NGINX` cannot start.
    # Port 80 also cannot be mapped directly to the `Certbot`
    # container because all the AAAA DNS records should be set to
    # the `NGINX` container to just have one entry point and for
    # the end user to not hassle with multiple IPv6 addresses.
    iptables -t nat -A PREROUTING -p tcp --dport 80 \
        -j DNAT --to-destination $CERTBOT_IPV4
    iptables -t nat -A POSTROUTING -p tcp -d $CERTBOT_IPV4 --dport 80 \
        -j SNAT --to-source $NGINX_IPV4
    if [[ $ENABLE_IPV6 == true ]]; then
        ip6tables -t nat -A PREROUTING -p tcp --dport 80 \
            -j DNAT --to-destination $CERTBOT_IPV6
        ip6tables -t nat -A POSTROUTING -p tcp -d $CERTBOT_IPV6 --dport 80 \
            -j SNAT --to-source $NGINX_IPV6
    fi
fi
