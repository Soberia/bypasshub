#!/usr/bin/env bash

trap 'exit' TERM INT

# Generates an OCSP response
generate_ocsp() {
    ocsptool \
        --ask \
        --load-cert /etc/letsencrypt/live/$DOMAIN/fullchain.pem \
        --load-issuer /etc/letsencrypt/live/$DOMAIN/chain.pem \
        --outfile /tmp/ocserv/ocsp.der &>/dev/null
}

install -d -m 0755 --owner ocserv --group ocserv /tmp/ocserv
rm -f /tmp/ocserv/ocserv.sock.* &>/dev/null
ln -s /dev/shm/passwd /tmp/ocserv/passwd &>/dev/null
cp -f /etc/ocserv/ocserv.conf /tmp/ocserv/ocserv.conf

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
if [[ $ENABLE_IPV6 == true ]]; then
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

# Injecting the environment variables
OCSERV_KEY=$(< /run/secrets/ocserv_key)
CAMOUFLAGE=$([ -z "$OCSERV_KEY" ] && echo false || echo true)
declare -a envs=(
    'DOMAIN'
    'OCSERV_KEY'
    'OCSERV_DTLS_PORT'
    'OCSERV_IPV4_SUBNET'
    'OCSERV_IPV6_SUBNET'
    'OCSERV_CLIENTS_IPV6_CIDR'
    'BIND_IPV4'
    'BIND_IPV6'
    'CAMOUFLAGE'
)
for env in "${envs[@]}"; do
    if [[ $env == *"IPV6"* && ( $ENABLE_IPV6 != true || -z ${!env} ) ]]; then
        sed -i "/\$$env\b/d" /tmp/ocserv/ocserv.conf
    else
        sed -i "s|\$$env\b|${!env}|g" /tmp/ocserv/ocserv.conf
    fi
done

# Periodically generating the OCSP response
while true; do
    generate_ocsp
    sleep 3600
done &

# Periodically reloading the regenerated certificate
last_renewal=$(cat /tmp/certbot/last-renewal 2>/dev/null)
while true; do
    if [ -z $last_renewal ]; then
        # The container restarted while `Certbot` container is starting
        sleep 1
        last_renewal=$(cat /tmp/certbot/last-renewal 2>/dev/null)
        continue
    fi

    sleep 3600
    current_renewal=$(cat /tmp/certbot/last-renewal 2>/dev/null)
    if (( $current_renewal > $last_renewal )); then
        generate_ocsp
        kill -HUP $(< /tmp/ocserv/ocserv.pid)
        last_renewal=$current_renewal
    fi
done &

# Starting the message broker
socket=/tmp/ocserv/message-broker.sock
socat -b16384 -t999 \
    UNIX-LISTEN:$socket,fork,reuseaddr,unlink-early,user=ocserv,group=ocserv,mode=766 \
    EXEC:/usr/local/sbin/message-broker.sh &

# Creating a TUN device
mkdir -p /dev/net
mknod /dev/net/tun c 10 200
chmod 600 /dev/net/tun

# Waiting for the users list to be generated
current_time=$(date '+%s')
for (( timeout=50; timeout > 0; timeout-- )); do
    [ -s /tmp/bypasshub/last-generate ] &&
        (( $(< /tmp/bypasshub/last-generate) >= $current_time )) &&
        break
    sleep 0.1
done

# Injecting the users
> /dev/shm/passwd
readarray -t users < /tmp/bypasshub/users
if [ ! -z "${users}" ]; then
    for user in "${users[@]}"; do
        user=($user)
        ocpasswd --passwd /dev/shm/passwd \
            ${user[0]} <<< ${user[1]}$'\n'${user[1]};
    done
    unset users user
fi

exec ocserv \
    --log-stderr \
    --foreground \
    --config /tmp/ocserv/ocserv.conf
