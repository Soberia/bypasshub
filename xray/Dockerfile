FROM ubuntu:rolling

SHELL ["bash", "-c"]
RUN apt-get update && \
    apt-get install -y curl unzip; \
    apt-get install -y --no-install-recommends jq iptables sudo; \
    #
    version=$(curl -sS https://api.github.com/repos/XTLS/Xray-core/releases/latest | \
        sed 'y/,/\n/' | \
        grep 'tag_name' | \
        awk -F '"' '{print $4}' \
    ); \
    if [[ -z $version ]]; then \
        >&2 echo "Can't find the latest Xray version number!"; \
        exit 1; \
    fi; \
    #
    mkdir /tmp/xray && cd /tmp/xray; \
    curl -sSL -o archive.zip \
        "https://github.com/XTLS/Xray-core/releases/download/$version/Xray-linux-64.zip"; \
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
    if [[ $ENABLE_IPV6 == 'true' && ! -z $IPV6_SUBNET && ! -z $BIND_IPV6 ]]; then \
        sudo ip6tables -A OUTPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT; \
        sudo ip6tables -A OUTPUT -d $BIND_IPV6 -p udp --dport 53 -j ACCEPT; \
        sudo ip6tables -A OUTPUT -d $BIND_IPV6 -p tcp --dport 53 -j ACCEPT; \
        sudo ip6tables -A OUTPUT -d $IPV6_SUBNET,fd00::/8 -j DROP; \
    fi; \

    rm -f /tmp/xray/*.sock >/dev/null 2>&1; \
    install -d -m 0755 /tmp/xray; \

    # Injecting the passwords
    vless_clients=""; \
    trojan_clients=""; \
    readarray -t passwords < /var/run/secrets/password; \
    if [ ! -z "${passwords}" ]; then \
        for password in "${passwords[@]}"; do \
            vless_clients+="{\"flow\": \"xtls-rprx-vision\",\"id\": \"$password\"},"; \
            trojan_clients+="{\"flow\": \"xtls-rprx-direct\",\"password\": \"$password\"},"; \
        done; \
        jq ".inbounds[0].settings.clients += [${vless_clients::-1}] | \
            .inbounds[1].settings.clients += [${trojan_clients::-1}]" \
            /usr/local/etc/xray/xray.json > /tmp/xray/xray.json; \
        unset passwords clients; \
    else \
        cp -f /usr/local/etc/xray/xray.json /tmp/xray/xray.json; \
    fi; \

    # Injecting the environment variables
    sed -i "s|\$DOMAIN|$DOMAIN|g" /tmp/xray/xray.json; \

    /usr/local/bin/xray run -config /tmp/xray/xray.json;
