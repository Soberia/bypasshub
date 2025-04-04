#!/usr/bin/env sh

# Configuring the firewall and rejecting clients
# access to the host and container's network
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
iptables -A INPUT -i lo -j ACCEPT
iptables -A INPUT -i eth0 -p tcp --dport 443 -j ACCEPT
iptables -A INPUT -i eth0 -p udp --dport $OCSERV_DTLS_PORT -j ACCEPT
iptables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
iptables -A FORWARD -i eth0 -d $OCSERV_IPV4_SUBNET -j ACCEPT
iptables -A FORWARD -s $OCSERV_IPV4_SUBNET -o eth0 -d $BIND_IPV4 -p udp --dport 53 -j ACCEPT
iptables -A FORWARD -s $OCSERV_IPV4_SUBNET -o eth0 -d $BIND_IPV4 -p tcp --dport 53 -j ACCEPT
iptables -A FORWARD -s $OCSERV_IPV4_SUBNET -o eth0 -d 10.0.0.0/8,172.16.0.0/12,192.168.0.0/16 -j DROP
iptables -A FORWARD -s $OCSERV_IPV4_SUBNET -o eth0 -j ACCEPT
iptables -t nat -A POSTROUTING -s $OCSERV_IPV4_SUBNET -o eth0 -j MASQUERADE

ip6tables -P INPUT DROP
ip6tables -P FORWARD DROP
ip6tables -A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
ip6tables -A INPUT -i lo -j ACCEPT
ip6tables -A INPUT -i eth0 -p ipv6-icmp -j ACCEPT
if [ "$ENABLE_IPV6" = true ]; then
    ip6tables -A INPUT -i eth0 -s $IPV6_SUBNET -p tcp --dport 443 -j ACCEPT
    ip6tables -A INPUT -i eth0 -s $IPV6_SUBNET -p udp --dport $OCSERV_DTLS_PORT -j ACCEPT
    ip6tables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
    ip6tables -A FORWARD -i eth0 -d $OCSERV_IPV6_SUBNET -j ACCEPT
    ip6tables -A FORWARD -s $OCSERV_IPV6_SUBNET -o eth0 -d $BIND_IPV6 -p udp --dport 53 -j ACCEPT
    ip6tables -A FORWARD -s $OCSERV_IPV6_SUBNET -o eth0 -d $BIND_IPV6 -p tcp --dport 53 -j ACCEPT
    ip6tables -A FORWARD -s $OCSERV_IPV6_SUBNET -o eth0 -d $NGINX_IPV6 -p tcp --dport $TLS_PORT -j ACCEPT
    ip6tables -A FORWARD -s $OCSERV_IPV6_SUBNET -o eth0 -d $IPV6_SUBNET,fd00::/8 -j DROP
    ip6tables -A FORWARD -s $OCSERV_IPV6_SUBNET -o eth0 -j ACCEPT
fi

# Performing stateless NAT on the outgoing packets to
# change the source IP address to the `NGINX` container.
# The binary mask required to match only a single port.
tc qdisc add dev eth0 root handle 10: htb
tc filter add dev eth0 parent 10: protocol ip prio 10 u32 \
    match ip src $OCSERV_IPV4 \
    match ip sport $OCSERV_DTLS_PORT 0xffff \
    action nat egress $OCSERV_IPV4 $NGINX_IPV4
