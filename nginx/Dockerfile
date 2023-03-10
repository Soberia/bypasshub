FROM nginx:stable
RUN apt-get update && \
    apt-get install -y --no-install-recommends iptables sudo; \
    apt-get clean; \
    echo 'nginx ALL=(root) NOPASSWD:/usr/sbin/ip6tables' >> /etc/sudoers;

USER nginx
SHELL ["bash", "-c"]
CMD \
    # Without this, default entrypoint scripts won't run
    /docker-entrypoint.sh nginx -v; \

    # Configuring the firewall
    sudo ip6tables -P INPUT DROP; \
    sudo ip6tables -P FORWARD DROP; \
    sudo ip6tables -A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT; \
    sudo ip6tables -A INPUT -i lo -j ACCEPT; \
    sudo ip6tables -A INPUT -i eth0 -p ipv6-icmp -j ACCEPT; \
    sudo ip6tables -A INPUT -i eth0 -p tcp --dport $TLS_PORT -j ACCEPT; \
    if [[ $COMPOSE_PROFILES == *"ocserv"* ]]; then \
        sudo ip6tables -A INPUT -i eth0 -p udp --dport $OCSERV_DTLS_PORT -j ACCEPT; \
    fi; \
    if [[ $ENABLE_IPV6 == 'true' ]] && [ ! -z $IPV6_SUBNET ]; then \
        if [[ $ENABLE_AUTHORITATIVE_ZONE == 'true' ]]; then \
            sudo ip6tables -A INPUT -i eth0 -p udp --dport 53 -j ACCEPT; \
            sudo ip6tables -A INPUT -i eth0 -p tcp --dport 53 -j ACCEPT; \
        fi; \
        sudo ip6tables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT; \
        sudo ip6tables -A FORWARD -d $IPV6_SUBNET -j ACCEPT; \
    fi; \

    rm -f /tmp/nginx/*.sock >/dev/null 2>&1; \
    install -d -m 0775 /tmp/nginx /tmp/nginx/cache; \
    cp /etc/nginx/nginx.conf /tmp/nginx/nginx.conf; \

    # Finding local DNS resolver IP address
    DNS_RESOLVER=$(sed -nr 's/.*(127.*)/\1/p' /etc/resolv.conf); \

    # Removing disabled profiles
    declare -a profiles=('xray' 'ocserv'); \
    [[ $ENABLE_AUTHORITATIVE_ZONE != 'true' ]] && profiles+=('bind'); \
    for profile in "${profiles[@]}"; do \
        if [[ $COMPOSE_PROFILES != *"$profile"* ]]; then \
            sed -i -e "/#! $profile/,/}/d" -e "/#? $profile/d" /tmp/nginx/nginx.conf; \
        fi; \
    done; \

    # Injecting the environment variables
    declare -a envs=( \
        'DOMAIN' \
        'XRAY_SNI' \
        'OCSERV_SNI' \
        'OCSERV_DTLS_PORT' \
        'TLS_PORT' \
        'DNS_IPV4' \
        'DNS_IPV6' \
        'DNS_RESOLVER' \
    ); \
    if [[ $ENABLE_IPV6 != 'true' || -z $DNS_IPV6 ]]; then \
        sed -i 's/\[\$DNS_IPV6\]//' /tmp/nginx/nginx.conf; \
    fi; \
    for env in "${envs[@]}"; do \
        sed -i "s|\$$env|${!env}|g" /tmp/nginx/nginx.conf; \
    done; \

    # Daily clearing the logs
    due_date=$(date '+%s' -d "+1 days"); \
    while true; do \
        if [ $(date '+%s') -gt $due_date ]; then \
            echo -n | tee /tmp/nginx/{access,error,static}.log >/dev/null; \
            kill -USR1 $(cat /tmp/nginx/nginx.pid); \
            due_date=$(date '+%s' -d "+1 days"); \
        fi; \
        sleep 60; \
    done & \

    nginx -c /tmp/nginx/nginx.conf -g 'daemon off;'
