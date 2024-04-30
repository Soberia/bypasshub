FROM nginx:mainline as nginx
RUN apt-get update && \
    apt-get install -y wget git make cmake gcc libpcre3-dev zlib1g-dev; \
    wget http://nginx.org/download/nginx-$NGINX_VERSION.tar.gz; \
    tar xf nginx-$NGINX_VERSION.tar.gz; \
    cd nginx-$NGINX_VERSION; \
    git clone --recurse-submodules -j8 --depth 1 https://github.com/google/ngx_brotli.git; \
    mkdir ngx_brotli/deps/brotli/out && cd ngx_brotli/deps/brotli/out; \
    flags="-Ofast -m64 -march=native -mtune=native -flto -funroll-loops -ffunction-sections -fdata-sections -Wl,--gc-sections"; \
    cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS="$flags" -DCMAKE_CXX_FLAGS="$flags" -DCMAKE_INSTALL_PREFIX=./installed ..; \
    cmake --build . --config Release --target brotlienc; \
    cd ../../../..; \
    ./configure --with-compat --add-dynamic-module=ngx_brotli; \
    make modules;

FROM nginx:mainline
LABEL org.opencontainers.image.title=NGINX
COPY --chmod=644 --from=nginx /nginx*/objs/*.so /usr/lib/nginx/modules/
RUN apt-get update && \
    apt-get install -y --no-install-recommends iptables sudo; \
    apt-get clean; \
    #
    echo 'nginx ALL=(root) NOPASSWD:/usr/sbin/iptables, /usr/sbin/ip6tables' >> /etc/sudoers;

USER nginx
SHELL ["bash", "-c"]
ENTRYPOINT trap 'exit' TERM INT; \
    install -d -m 0755 /tmp/nginx/{cache,log}; \
    rm -f /tmp/nginx/*.sock >/dev/null 2>&1; \
    cp /etc/nginx/nginx.conf /tmp/nginx/nginx.conf; \

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
    if [[ $ENABLE_IPV6 == true ]]; then \
        sudo ip6tables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT; \
        sudo ip6tables -A FORWARD -d $IPV6_SUBNET -j ACCEPT; \
    fi; \

    if [[ $ENABLE_CERTBOT_HTTP_MODE == true ]]; then \
        # Redirecting the traffic to the `Certbot` container.
        # It's not possible to forward the traffic from the `NGINX`
        # process itself to the `Certbot` container because the TLS
        # certificate probably is not generated just yet and the
        # `NGINX` cannot start.
        # Port 80 also cannot be mapped directly to the `Certbot`
        # container because all the AAAA DNS records should be set to
        # the `NGINX` container to just have one entry point and for
        # the end user to not hassle with multiple IPv6 addresses.
        sudo iptables -t nat -A PREROUTING -p tcp --dport 80 \
            -j DNAT --to-destination $CERTBOT_IPV4; \
        sudo iptables -t nat -A POSTROUTING -p tcp -d $CERTBOT_IPV4 --dport 80 \
            -j SNAT --to-source $NGINX_IPV4; \
        if [[ $ENABLE_IPV6 == true ]]; then \
            sudo ip6tables -t nat -A PREROUTING -p tcp --dport 80 \
                -j DNAT --to-destination $CERTBOT_IPV6; \
            sudo ip6tables -t nat -A POSTROUTING -p tcp -d $CERTBOT_IPV6 --dport 80 \
                -j SNAT --to-source $NGINX_IPV6; \
        fi; \
    fi; \

    # Removing the disabled profiles
    for profile in 'xray' 'ocserv'; do \
        if [[ $COMPOSE_PROFILES != *"$profile"* ]]; then \
            sed -i -e "/#! $profile/,/}/d" -e "/#? $profile/d" /tmp/nginx/nginx.conf; \
        fi; \
    done; \

    # Injecting the environment variables
    DNS_RESOLVER=$(sed -nr 's/.*(127.*)/\1/p; //q' /etc/resolv.conf); \
    declare -a envs=( \
        'DOMAIN' \
        'XRAY_SNI' \
        'XRAY_CDN_SNI' \
        'OCSERV_SNI' \
        'OCSERV_DTLS_PORT' \
        'TLS_PORT' \
        'DNS_IPV4' \
        'DNS_IPV6' \
        'DNS_RESOLVER' \
    ); \
    if [[ $ENABLE_IPV6 != true || -z $DNS_IPV6 ]]; then \
        sed -i 's/\[\$DNS_IPV6\]//' /tmp/nginx/nginx.conf; \
    fi; \
    for env in "${envs[@]}"; do \
        sed -i "s|\$$env|${!env}|g" /tmp/nginx/nginx.conf; \
    done; \

    # Periodically clearing the logs
    if [ ! -z $NGINX_LOG_PURGE_INTERVAL ] && (( $NGINX_LOG_PURGE_INTERVAL > 0 )); then \
        if [ ! -f /tmp/nginx/log/last-purge ]; then \
            last_purge=$(date '+%s'); \
            echo $last_purge > /tmp/nginx/log/last-purge; \
        else \
            last_purge=$(< /tmp/nginx/log/last-purge); \
        fi; \

        while true; do \
            due_date=$(( $last_purge + $NGINX_LOG_PURGE_INTERVAL )); \
            sleep_time=$NGINX_LOG_PURGE_INTERVAL; \
            current_time=$(date '+%s'); \
            if (( $current_time >= $due_date )); then \
                echo -n | tee /tmp/nginx/log/{access,error,static,api}.log >/dev/null; \
                kill -USR1 $(< /tmp/nginx/nginx.pid); \
                last_purge=$current_time; \
                echo $current_time > /tmp/nginx/log/last-purge; \
            else \
                sleep_time=$(( $due_date - $current_time )); \
            fi; \
            sleep $sleep_time; \
        done & \
    fi; \

    # Periodically reloading the regenerated certificate
    if [[ $ENABLE_CERTBOT_HTTP_MODE == true ]]; then \
        while [ ! -f /tmp/certbot/last-renewal ]; do \
            sleep 0.1 & wait $!; \
        done; \
    fi; \
    last_renewal=$(cat /tmp/certbot/last-renewal 2>/dev/null); \
    while true; do \
        if [ -z $last_renewal ]; then \
            # The container restarted while `Certbot` container is starting
            sleep 1; \
            last_renewal=$(cat /tmp/certbot/last-renewal 2>/dev/null); \
            continue; \
        fi; \

        sleep 3600; \
        current_renewal=$(cat /tmp/certbot/last-renewal 2>/dev/null); \
        if (( $current_renewal > $last_renewal )); then \
            kill -HUP $(< /tmp/nginx/nginx.pid); \
            last_renewal=$current_renewal; \
        fi; \
    done & \

    # Waiting for the services to start to avoid
    # spamming the logs with connection errors
    for profile in "xray" "ocserv"; do \
        if [[ $COMPOSE_PROFILES == *"$profile"* ]]; then \
            for (( timeout=50; timeout > 0; timeout-- )); do \
                case $profile in \
                    "xray") [ -S /tmp/xray/api.sock ] && break ;; \
                    "ocserv") [ -S /tmp/ocserv/ocserv.sock* ] && break ;; \
                esac; \
                sleep 0.1; \
            done; \
        fi; \
    done; \

    exec nginx -c /tmp/nginx/nginx.conf -g 'daemon off;'
