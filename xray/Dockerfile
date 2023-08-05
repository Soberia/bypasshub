ARG VERSION=1.8.3

FROM ubuntu:rolling
ARG VERSION
SHELL ["bash", "-c"]
RUN apt-get update && \
    apt-get install -y curl unzip; \
    apt-get install -y --no-install-recommends jq iptables sudo; \
    #
    mkdir /tmp/xray && cd /tmp/xray; \
    curl -sSL -o archive.zip \
        "https://github.com/XTLS/Xray-core/releases/download/v$VERSION/Xray-linux-64.zip"; \
    unzip archive.zip; \
    install -m 755 xray /usr/local/bin/xray; \
    install -d /usr/local/share/xray; \
    install -m 644 geoip.dat /usr/local/share/xray; \
    install -m 644 geosite.dat /usr/local/share/xray; \
    rm -r $PWD; \
    #
    apt-get --purge -y remove curl unzip && \
    apt-get -y autoremove; \
    apt-get clean; \
    #
    useradd --gid proxy xray; \
    echo 'xray ALL=(root) NOPASSWD: /usr/sbin/iptables, /usr/sbin/ip6tables' >> /etc/sudoers;

USER xray
CMD \
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
    if [[ $ENABLE_IPV6 == 'true' && ! -z $IPV6_SUBNET ]] && \
        [ ! -z $BIND_IPV6 && ! -z $NGINX_IPV6 ]; then \
        sudo ip6tables -A OUTPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT; \
        sudo ip6tables -A OUTPUT -d $BIND_IPV6 -p udp --dport 53 -j ACCEPT; \
        sudo ip6tables -A OUTPUT -d $BIND_IPV6 -p tcp --dport 53 -j ACCEPT; \
        sudo ip6tables -A OUTPUT -d $NGINX_IPV6 -p tcp --dport $TLS_PORT -j ACCEPT; \
        sudo ip6tables -A OUTPUT -d $IPV6_SUBNET,fd00::/8 -j DROP; \
    fi; \

    > /tmp/xray/uuids; \
    > /tmp/xray/urls.txt; \
    install -d -m 0755 /tmp/xray; \
    rm -f /tmp/xray/*.sock >/dev/null 2>&1; \
    cp -f /usr/local/etc/xray/xray.json /tmp/xray/xray.json; \

    # Generateing subscription share URLs
    if [[ $ENABLE_XRAY_SUBSCRIPTION == 'true' ]]; then \
        shared="?security=tls&fp=randomized"; \
		url_tcp="@${XRAY_SNI}:${TLS_PORT}${shared}&type=tcp&flow=xtls-rprx-vision#${DOMAIN}"; \
        echo "vless://{uuid}${url_tcp}" >> /tmp/xray/urls.txt; \
        if [[ $ENABLE_XRAY_CDN == 'true' ]]; then \
            cdn_port=$([ ! -z "${CDN_TLS_PORT}" ] && echo $CDN_TLS_PORT || echo $TLS_PORT); \
            url_ws=":${cdn_port}${shared}&type=ws&sni=${XRAY_CDN_SNI}"; \
		    url_ws="${url_ws}&host=${XRAY_CDN_SNI}&path=/ws?ed=2048#${DOMAIN}-CDN"; \
            echo "vless://{uuid}@${XRAY_CDN_SNI}${url_ws}" >> /tmp/xray/urls.txt; \
            if [ -f /usr/local/etc/xray/confs/cdn-ips ]; then \
                readarray -t ips < /usr/local/etc/xray/confs/cdn-ips; \
                if [ ! -z "${ips}" ]; then \
                    for ip in "${ips[@]}"; do \
                        if [ ! -z "${ip// }" ]; then \
                            ip=($ip); \
                            echo "vless://{uuid}@${ip[0]}${url_ws}-${ip[1]}" \
                                >> /tmp/xray/urls.txt; \
                        fi; \
                    done; \
                fi; \
            fi; \
        fi; \
    fi; \

    # Injecting the environment variables
    sed -i "s|\$DOMAIN|$DOMAIN|g" /tmp/xray/xray.json; \

    # Waiting for the users to be generated
    timeout=5; \
    current_time=$(date '+%s'); \
    while (( $timeout > 0 )); do \
        if [ -s /tmp/bypasshub/last-generate ] && \
            (( $(< /tmp/bypasshub/last-generate) >= $current_time )); then \
            break; \
        fi; \

        (( timeout-- )); \
        sleep 1; \
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
            if [[ $ENABLE_XRAY_CDN == 'true' ]]; then \
                clients_ws+="{\"flow\":null,$shared},"; \
            fi; \
            if [[ $ENABLE_XRAY_SUBSCRIPTION == 'true' ]]; then \
                echo "${user[0]} ${user[0]};" >> /tmp/xray/uuids; \
            fi; \
        done; \
        [[ $ENABLE_XRAY_CDN != 'true' ]] && clients_ws=','; \
        json=$(jq \
            ".inbounds[1].settings.clients += [${clients_tcp::-1}] | \
            .inbounds[2].settings.clients += [${clients_ws::-1}]" \
            /tmp/xray/xray.json \
        ); \
        echo -E "$json" > /tmp/xray/xray.json; \
        unset users user shared json clients_tcp clients_ws; \
    fi; \

    /usr/local/bin/xray run \
        -config /tmp/xray/xray.json \
        -confdir /usr/local/etc/xray/confs
