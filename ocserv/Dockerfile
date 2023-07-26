ARG VERSION=1.1.7

FROM ubuntu:rolling AS ocserv
ARG VERSION
RUN apt-get update && \
    apt-get install -y wget xz-utils make gcc pkg-config autoconf automake \
        nettle-dev libgnutls30 libgnutls28-dev libev-dev \
        libseccomp-dev libreadline-dev libnl-route-3-dev; \
    wget https://www.infradead.org/ocserv/download/ocserv-$VERSION.tar.xz; \
    tar xf ocserv-$VERSION.tar.xz; \
    cd ocserv-$VERSION; \
    #
    autoreconf -fvi; \
    ./configure --disable-systemd --disable-compression \
        --without-root-tests --without-asan-broken-tests \
        --without-nuttcp-tests --without-tun-tests \
        --without-http-parser --without-protobuf --without-maxmind \
        --without-geoip --without-liboath --without-pam --without-radius \
        --without-gssapi --without-pcl-lib --without-utmp \
        --without-libwrap --without-lz4 --with-local-talloc \
        --with-pager=""; \
    make && make install;

FROM ubuntu:rolling
COPY --chmod=550 *.sh /usr/local/sbin/
COPY --from=ocserv /usr/local/bin/ /usr/local/bin/
COPY --from=ocserv /usr/local/sbin/ocserv* /usr/local/sbin/
RUN apt-get update && \
    apt-get install -y --no-install-recommends iptables iproute2 \
        gnutls-bin libgnutls28-dev libev-dev libseccomp-dev \
        libreadline-dev libnl-route-3-dev && \
    apt-get clean; \
    #
    useradd --system --user-group --no-create-home --home-dir /tmp/ocserv \
        --shell /usr/sbin/nologin --uid 102 ocserv;

SHELL ["bash", "-c"]
CMD \
    # Configuring the firewall and rejecting clients
    # access to the host and container's network
    iptables -P INPUT DROP; \
    iptables -P FORWARD DROP; \
    iptables -A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT; \
    iptables -A INPUT -i lo -j ACCEPT; \
    iptables -A INPUT -i eth0 -p tcp --dport 443 -j ACCEPT; \
    iptables -A INPUT -i eth0 -p udp --dport $OCSERV_DTLS_PORT -j ACCEPT; \
    if [ ! -z $OCSERV_IPV4_SUBNET ]; then \
        iptables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT; \
        iptables -A FORWARD -i eth0 -d $OCSERV_IPV4_SUBNET -j ACCEPT; \
        iptables -A FORWARD -s $OCSERV_IPV4_SUBNET -o eth0 -d $BIND_IPV4 -p udp --dport 53 -j ACCEPT; \
        iptables -A FORWARD -s $OCSERV_IPV4_SUBNET -o eth0 -d $BIND_IPV4 -p tcp --dport 53 -j ACCEPT; \
        iptables -A FORWARD -s $OCSERV_IPV4_SUBNET -o eth0 -d 10.0.0.0/8,172.16.0.0/12,192.168.0.0/16 -j DROP; \
        iptables -A FORWARD -s $OCSERV_IPV4_SUBNET -o eth0 -j ACCEPT; \
        iptables -t nat -A POSTROUTING -s $OCSERV_IPV4_SUBNET -o eth0 -j MASQUERADE; \
    fi; \

    ip6tables -P INPUT DROP; \
    ip6tables -P FORWARD DROP; \
    ip6tables -A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT; \
    ip6tables -A INPUT -i lo -j ACCEPT; \
    ip6tables -A INPUT -i eth0 -p ipv6-icmp -j ACCEPT; \
    if [[ $ENABLE_IPV6 == 'true' && ! -z $IPV6_SUBNET ]] && \
        [ ! -z $OCSERV_IPV6_SUBNET && ! -z $BIND_IPV6 && ! -z $NGINX_IPV6 ]; then \
        ip6tables -A INPUT -i eth0 -s $IPV6_SUBNET -p tcp --dport 443 -j ACCEPT; \
        ip6tables -A INPUT -i eth0 -s $IPV6_SUBNET -p udp --dport $OCSERV_DTLS_PORT -j ACCEPT; \
        ip6tables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT; \
        ip6tables -A FORWARD -i eth0 -d $OCSERV_IPV6_SUBNET -j ACCEPT; \
        ip6tables -A FORWARD -s $OCSERV_IPV6_SUBNET -o eth0 -d $BIND_IPV6 -p udp --dport 53 -j ACCEPT; \
        ip6tables -A FORWARD -s $OCSERV_IPV6_SUBNET -o eth0 -d $BIND_IPV6 -p tcp --dport 53 -j ACCEPT; \
        ip6tables -A FORWARD -s $OCSERV_IPV6_SUBNET -o eth0 -d $NGINX_IPV6 -p tcp --dport $TLS_PORT -j ACCEPT; \
        ip6tables -A FORWARD -s $OCSERV_IPV6_SUBNET -o eth0 -d $IPV6_SUBNET,fd00::/8 -j DROP; \
        ip6tables -A FORWARD -s $OCSERV_IPV6_SUBNET -o eth0 -j ACCEPT; \
    fi; \

    install -d -m 0755 --owner ocserv --group ocserv /tmp/ocserv; \
    rm -f /tmp/ocserv/ocserv.sock.* >/dev/null 2>&1; \
    cp /etc/ocserv/ocserv.conf /tmp/ocserv/ocserv.conf; \

    # Injecting the environment variables
    declare -a envs=( \
        'DOMAIN' \
        'OCSERV_DTLS_PORT' \
        'OCSERV_IPV4_SUBNET' \
        'OCSERV_IPV6_SUBNET' \
        'OCSERV_CLIENTS_IPV6_CIDR' \
        'BIND_IPV4' \
        'BIND_IPV6' \
    ); \
    for env in "${envs[@]}"; do \
        if [[ $env == *"IPV6"* && ( $ENABLE_IPV6 != 'true' || -z ${!env} ) ]]; then \
            sed -i "/\$$env/d" /tmp/ocserv/ocserv.conf; \
        else \
            sed -i "s|\$$env|${!env}|g" /tmp/ocserv/ocserv.conf; \
        fi; \
    done; \

    # Generating OCSP for stapling
    while true; do \
        ocsptool \
            --ask \
            --load-cert /etc/letsencrypt/live/$DOMAIN/fullchain.pem \
            --load-issuer /etc/letsencrypt/live/$DOMAIN/chain.pem \
            --outfile /tmp/ocserv/ocsp.der; \
        sleep 3600; \
    done & \

    # Creating a TUN device
    mkdir -p /dev/net; \
    mknod /dev/net/tun c 10 200; \
    chmod 600 /dev/net/tun; \

    ocserv --foreground --config /tmp/ocserv/ocserv.conf
