#!/usr/bin/env sh

# Configuring the firewall and rejecting clients
# access to the host and container's network
for ip in ip ip6; do
    ${ip}tables -P FORWARD DROP
    ${ip}tables -P INPUT DROP
    ${ip}tables -A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
    ${ip}tables -A INPUT -i lo -j ACCEPT
done

iptables -A OUTPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
iptables -A OUTPUT -d $BIND_IPV4 -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -d $BIND_IPV4 -p tcp --dport 53 -j ACCEPT
iptables -A OUTPUT -d 10.0.0.0/8,172.16.0.0/12,192.168.0.0/16 -j DROP

ip6tables -A INPUT -i eth0 -p ipv6-icmp -j ACCEPT
if [ "$ENABLE_IPV6" = true ]; then
    ip6tables -A OUTPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
    ip6tables -A OUTPUT -d $BIND_IPV6 -p udp --dport 53 -j ACCEPT
    ip6tables -A OUTPUT -d $BIND_IPV6 -p tcp --dport 53 -j ACCEPT
    ip6tables -A OUTPUT -d $NGINX_IPV6 -p tcp --dport $TLS_PORT -j ACCEPT
    ip6tables -A OUTPUT -d $IPV6_SUBNET,fd00::/8 -j DROP
fi
