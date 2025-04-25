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

install -d -g users -m 0755 /tmp/ocserv
rm -f /tmp/ocserv/ocserv.sock.* &>/dev/null
ln -s /dev/shm/passwd /tmp/ocserv/passwd &>/dev/null
cp -f /etc/ocserv/ocserv.conf /tmp/ocserv/ocserv.conf

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
