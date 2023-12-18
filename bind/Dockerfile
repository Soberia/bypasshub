FROM ubuntu:rolling
LABEL org.opencontainers.image.title=BIND
RUN apt-get update && \
    apt-get install -y --no-install-recommends bind9 bind9utils dnsutils iptables sudo && \
    apt-get clean; \
    #
    ln -s /tmp/bind /run/named; \
    echo 'bind ALL=(root) NOPASSWD:/usr/sbin/ip6tables' >> /etc/sudoers;

USER bind
SHELL ["bash", "-c"]
CMD trap 'exit' TERM INT; \
    certbot_activated=$([[ $COMPOSE_PROFILES == *"certbot"* ]] && echo true || echo false); \
    install -d -m 0755 /tmp/bind/{cache,keys}; \
    cp /etc/bind/named.conf /tmp/bind/named.conf; \
    cp /etc/bind/db.forward /tmp/bind/db.forward; \
    if [ ! -f /tmp/bind/domain ]; then \
        echo $DOMAIN > /tmp/bind/domain; \
    elif [[ $(< /tmp/bind/domain) != $DOMAIN ]]; then \
        # The domain has been changed.
        # Removing previously generated signed zones.
        rm /tmp/bind/db.forward.* >/dev/null 2>&1; \
        rm /tmp/bind/keys/* >/dev/null 2>&1; \
        echo $DOMAIN > /tmp/bind/domain; \
    fi; \

    # Configuring the firewall
    sudo ip6tables -P INPUT DROP; \
    sudo ip6tables -P FORWARD DROP; \
    sudo ip6tables -A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT; \
    sudo ip6tables -A INPUT -i lo -j ACCEPT; \
    sudo ip6tables -A INPUT -i eth0 -p ipv6-icmp -j ACCEPT; \
    if [[ $ENABLE_IPV6 == true ]] && [[ ! -z $IPV6_SUBNET ]]; then \
        source=$([[ $certbot_activated == false ]] && echo "-s $IPV6_SUBNET" || echo ''); \
        sudo ip6tables -A INPUT -i eth0 $source -p tcp --dport 53 -j ACCEPT; \
        sudo ip6tables -A INPUT -i eth0 $source -p udp --dport 53 -j ACCEPT; \
    fi; \

    if [[ $ENABLE_AUTHORITATIVE_ZONE == true ]]; then \
        if [[ $ENABLE_DNSSEC == true ]]; then \
            if [ -z "$(ls -A /tmp/bind/keys)" ]; then \
                dnssec-keygen -K /tmp/bind/keys -a ECDSAP256SHA256 -3 $DOMAIN; \
                dnssec-keygen -K /tmp/bind/keys -a ECDSAP256SHA256 -3 -f KSK $DOMAIN; \
            fi; \
            # Periodically resigning the NSEC3 records
            # with a new salt to prevent domain walking
            while true; do \
                sleep 86400; \
                rndc signing -nsec3param 1 0 10 \
                    $(head /dev/urandom | sha1sum | head -c16) $DOMAIN; \
            done & \
        else \
            # Disabling DNSSEC signing
            sed -i "/#? dnssec/d" /tmp/bind/named.conf; \
        fi; \
    else \
        # Disabling authoritative mode
        sed -i "/#! authoritative/,/^}/d" /tmp/bind/named.conf; \
    fi; \

    # Removing records for disabled profiles or invalid
    # SNIs which is not part of the parent domain
    for profile in 'xray' 'ocserv'; do \
        sni="${profile^^}_SNI"; \
        if [[ $certbot_activated == false && $COMPOSE_PROFILES != *"$profile"* ]] || \
           [[ ! ${!sni} =~ "$DOMAIN"$ ]]; then \
            sed -i "/\$$sni/,+1d" /tmp/bind/db.forward; \
        fi; \
    done; \

    # Injecting the environment variables
    declare -a envs=( \
        'DOMAIN' \
        'XRAY_SNI' \
        'OCSERV_SNI' \
        'DNS_CACHE_SIZE' \
        'DNS_IPV4' \
        'DNS_IPV6' \
        'IPV6_SUBNET' \
        'PUBLIC_IPV4' \
        'NGINX_IPV4' \
        'NGINX_IPV6' \
    ); \
    for env in "${envs[@]}"; do \
        if [[ $env == *"IPV6"* && ( $ENABLE_IPV6 != true || -z ${!env} ) ]]; then \
            sed -i "/\$$env/d" /tmp/bind/{named.conf,db.forward}; \
        else \
            sed -i "s|\$$env|${!env}|g" /tmp/bind/{named.conf,db.forward}; \
        fi; \
    done; \

    exec /usr/sbin/named -f -c /tmp/bind/named.conf
