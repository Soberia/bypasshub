ARG VERSION=1.8.6

FROM ubuntu:rolling AS xray
ARG VERSION
RUN apt-get update && \
    apt-get install -y curl unzip; \
    curl -sSL -o archive.zip \
        "https://github.com/XTLS/Xray-core/releases/download/v$VERSION/Xray-linux-64.zip"; \
    unzip archive.zip;

FROM ubuntu:rolling
LABEL org.opencontainers.image.title=Xray-core
COPY --from=xray --chmod=755 /xray /usr/local/bin/xray
COPY --from=xray --chmod=644 /geo*.dat /usr/local/share/xray/
RUN apt-get update && \
    apt-get install -y --no-install-recommends jq iptables sudo; \
    apt-get clean; \
    #
    useradd --gid proxy xray; \
    echo 'xray ALL=(root) NOPASSWD:/usr/sbin/iptables, /usr/sbin/ip6tables' >> /etc/sudoers;

USER xray
SHELL ["bash", "-c"]
CMD trap 'exit' TERM INT; \
    install -d -m 0755 /tmp/xray; \
    rm -f /tmp/xray/*.sock >/dev/null 2>&1; \
    cp -f /usr/local/etc/xray/xray.json /tmp/xray/xray.json; \
    if [[ $ENABLE_XRAY_SUBSCRIPTION == true ]]; then \
        cp -f /usr/local/etc/xray/confs/cdn-ips /tmp/xray/cdn-ips 2>/dev/null; \
    fi; \

    # Configuring the firewall and rejecting clients
    # access to the host and container's network
    for ip in ip ip6; do \
        sudo ${ip}tables -P FORWARD DROP; \
        sudo ${ip}tables -P INPUT DROP; \
        sudo ${ip}tables -A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT; \
        sudo ${ip}tables -A INPUT -i lo -j ACCEPT; \
    done; \

    sudo iptables -A OUTPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT; \
    sudo iptables -A OUTPUT -d $BIND_IPV4 -p udp --dport 53 -j ACCEPT; \
    sudo iptables -A OUTPUT -d $BIND_IPV4 -p tcp --dport 53 -j ACCEPT; \
    sudo iptables -A OUTPUT -d 10.0.0.0/8,172.16.0.0/12,192.168.0.0/16 -j DROP; \

    sudo ip6tables -A INPUT -i eth0 -p ipv6-icmp -j ACCEPT; \
    if [[ $ENABLE_IPV6 == true && ! -z $IPV6_SUBNET ]] && \
        [[ ! -z $BIND_IPV6 && ! -z $NGINX_IPV6 ]]; then \
        sudo ip6tables -A OUTPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT; \
        sudo ip6tables -A OUTPUT -d $BIND_IPV6 -p udp --dport 53 -j ACCEPT; \
        sudo ip6tables -A OUTPUT -d $BIND_IPV6 -p tcp --dport 53 -j ACCEPT; \
        sudo ip6tables -A OUTPUT -d $NGINX_IPV6 -p tcp --dport $TLS_PORT -j ACCEPT; \
        sudo ip6tables -A OUTPUT -d $IPV6_SUBNET,fd00::/8 -j DROP; \
    fi; \

    # Injecting the environment variables
    sed -i "s|\$DOMAIN|$DOMAIN|g" /tmp/xray/xray.json; \

    # Waiting for the users to be generated
    timeout=50; \
    current_time=$(date '+%s'); \
    while (( $timeout > 0 )); do \
        if [ -s /tmp/bypasshub/last-generate ] && \
            (( $(< /tmp/bypasshub/last-generate) >= $current_time )); then \
            break; \
        fi; \

        (( timeout-- )); \
        sleep 0.1; \
    done; \

    # Injecting the users
    readarray -t users < /tmp/bypasshub/users; \
    if [ ! -z "${users}" ]; then \
        clients_tcp=""; \
        clients_ws=""; \
        for user in "${users[@]}"; do \
            user=($user); \
            shared="\"email\":\"${user[0]}@$DOMAIN\",\"id\":\"${user[1]}\""; \
            clients_tcp+="{\"flow\":\"xtls-rprx-vision\",$shared},"; \
            if [[ $ENABLE_XRAY_CDN == true ]]; then \
                clients_ws+="{\"flow\":null,$shared},"; \
            fi; \
        done; \
        [[ $ENABLE_XRAY_CDN != true ]] && clients_ws=','; \
        json=$(jq \
            ".inbounds[1].settings.clients += [${clients_tcp::-1}] | \
            .inbounds[2].settings.clients += [${clients_ws::-1}]" \
            /tmp/xray/xray.json \
        ); \
        echo -E "$json" > /tmp/xray/xray.json; \
        unset users user shared json clients_tcp clients_ws; \
    fi; \

    exec /usr/local/bin/xray run \
        -config /tmp/xray/xray.json \
        -confdir /usr/local/etc/xray/confs
