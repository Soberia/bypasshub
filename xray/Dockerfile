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
    script=/usr/local/bin/xray-user; \
    echo '#!/usr/bin/env bash' > $script; \
    echo 'username=$(echo $2 | tr "[:upper:]" "[:lower:]")' >> $script; \
    echo '[[ $username = *[[:space:]]* ]] && echo "Invalid username!" && exit 1' >> $script; \
    echo 'if [ $1 = "add" ]; then' >> $script; \
    echo '    grep -q " $username\$" /xray/password && echo "Username already exist!" && exit 1' >> $script; \
    echo '    uuid=$(xray uuid)' >> $script; \
    echo '    echo "$uuid $username" >> /xray/password' >> $script; \
    echo '    echo $uuid' >> $script; \
    echo 'elif [ $1 = "delete" ]; then' >> $script; \
    echo '    sed -i "/ $username\$/d" /xray/password' >> $script; \
    echo 'fi' >> $script; \
    chmod +x $script; \
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
    if [[ $ENABLE_IPV6 == 'true' && ! -z $IPV6_SUBNET && ! -z $BIND_IPV6 ]]; then \
        sudo ip6tables -A OUTPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT; \
        sudo ip6tables -A OUTPUT -d $BIND_IPV6 -p udp --dport 53 -j ACCEPT; \
        sudo ip6tables -A OUTPUT -d $BIND_IPV6 -p tcp --dport 53 -j ACCEPT; \
        sudo ip6tables -A OUTPUT -d $IPV6_SUBNET,fd00::/8 -j DROP; \
    fi; \

    > /tmp/xray/uuids; \
    > /tmp/xray/urls.txt; \
    rm -f /tmp/xray/*.sock >/dev/null 2>&1; \
    install -d -m 0755 /tmp/xray; \

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

    # Injecting the passwords
    clients_tcp=""; \
    clients_ws=""; \
    readarray -t passwords < /var/run/secrets/password; \
    if [ ! -z "${passwords}" ]; then \
        for line in "${passwords[@]}"; do \
            if [ ! -z "${line// }" ]; then \
                line=($line); \
                shared="\"email\": \"${line[1]}@$DOMAIN\",\"id\": \"${line[0]}\""; \
                clients_tcp+="{\"flow\": \"xtls-rprx-vision\",$shared},"; \
                if [[ $ENABLE_XRAY_CDN == 'true' ]]; then \
                    clients_ws+="{\"flow\": null,$shared},"; \
                fi; \
                if [[ $ENABLE_XRAY_SUBSCRIPTION == 'true' ]]; then \
                    echo "${line[0]} ${line[0]};" >> /tmp/xray/uuids; \
                fi; \
            fi; \
        done; \
        [[ $ENABLE_XRAY_CDN != 'true' ]] && clients_ws=','; \
        jq ".inbounds[0].settings.clients += [${clients_tcp::-1}] | \
            .inbounds[1].settings.clients += [${clients_ws::-1}]" \
            /usr/local/etc/xray/xray.json > /tmp/xray/xray.json; \
        unset passwords line shared clients_tcp clients_ws; \
    else \
        cp -f /usr/local/etc/xray/xray.json /tmp/xray/xray.json; \
    fi; \

    # Injecting the environment variables
    sed -i "s|\$DOMAIN|$DOMAIN|g" /tmp/xray/xray.json; \

    /usr/local/bin/xray run \
        -config /tmp/xray/xray.json \
        -confdir /usr/local/etc/xray/confs
