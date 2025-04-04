#!/usr/bin/env bash

trap 'exit' TERM INT

install -d -g users -m 0750 /tmp/nginx
install -d -m 0750 /tmp/nginx/cache
rm -f /tmp/nginx/*.sock &>/dev/null
cp /etc/nginx/nginx.conf /tmp/nginx/nginx.conf
[[ ! -f /etc/nginx/html/index.html ]] &&
    cp /etc/nginx/index.html /etc/nginx/html/

# Removing the disabled profiles
for profile in 'xray' 'ocserv'; do
    if [[ $COMPOSE_PROFILES != *"$profile"* ]]; then
        sed -i -e "/#! $profile/,/}/d" -e "/#? $profile/d" /tmp/nginx/nginx.conf
    fi
done

# Injecting the environment variables
DNS_RESOLVER=$(sed -nr 's/.*(127.*)/\1/p; //q' /etc/resolv.conf)
declare -a envs=(
    'DOMAIN'
    'XRAY_SNI'
    'XRAY_CDN_SNI'
    'OCSERV_SNI'
    'OCSERV_DTLS_PORT'
    'TLS_PORT'
    'DNS_RESOLVER'
    'OCSERV_IPV4'
)
for env in "${envs[@]}"; do
    sed -i "s|\$$env\b|${!env}|g" /tmp/nginx/nginx.conf
done

# Periodically clearing the logs
if [ ! -z $NGINX_LOG_PURGE_INTERVAL ] && (( $NGINX_LOG_PURGE_INTERVAL > 0 )); then
    if [ ! -f /var/log/nginx/last-purge ]; then
        last_purge=$(date '+%s')
        echo $last_purge > /var/log/nginx/last-purge
    else
        last_purge=$(< /var/log/nginx/last-purge)
    fi

    while true; do
        due_date=$(( $last_purge + $NGINX_LOG_PURGE_INTERVAL ))
        sleep_time=$NGINX_LOG_PURGE_INTERVAL
        current_time=$(date '+%s')
        if (( $current_time >= $due_date )); then
            tee /var/log/nginx/*.log </dev/null
            kill -USR1 $(< /tmp/nginx/nginx.pid)
            last_purge=$current_time
            echo $current_time > /var/log/nginx/last-purge
        else
            sleep_time=$(( $due_date - $current_time ))
        fi
        sleep $sleep_time
    done &
fi

# Periodically reloading the regenerated certificate
if [[ $ENABLE_CERTBOT_HTTP_MODE == true ]]; then
    while [ ! -f /tmp/certbot/last-renewal ]; do
        sleep 0.1 & wait $!
    done
fi
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
        kill -HUP $(< /tmp/nginx/nginx.pid)
        last_renewal=$current_renewal
    fi
done &

# Waiting for the services to start to avoid
# spamming the logs with connection errors
for profile in "xray" "ocserv"; do
    if [[ $COMPOSE_PROFILES == *"$profile"* ]]; then
        for (( timeout=50; timeout > 0; timeout-- )); do
            case $profile in
                "xray") [ -S /tmp/xray/api.sock ] && break ;;
                "ocserv") [ -S $(set -- /tmp/ocserv/ocserv.sock*; echo $1) ] &&
                    break ;;
            esac
            sleep 0.1
        done
    fi
done

exec nginx -c /tmp/nginx/nginx.conf -g 'daemon off;'
