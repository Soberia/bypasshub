# As mentioned in the Docker documents, if the `ARG` variable
# is contained for example in the `RUN` command, then the
# build cache should be invalidated on the value change
# of the variable, but that's not working as supposed to be.
# As a result, the right Certbot DNS plugin will not be selected
# as the base image if the container was previously built with
# the other plugins. The only solution is to either remove the
# image manually or recreate the container without the cache.
ARG PLUGIN
FROM certbot/dns-$PLUGIN
LABEL org.opencontainers.image.title=Certbot
RUN apk add --no-cache bash sudo; \
    adduser -HD certbot certbot; \
    echo -n 'certbot ALL=(root) NOPASSWD:/bin/cat /tmp/bind/session.key' >> /etc/sudoers; \
    echo -n ', /bin/chown * /etc/letsencrypt' >> /etc/sudoers; \
    echo ', /bin/chmod * /etc/letsencrypt*' >> /etc/sudoers;

USER certbot
ENTRYPOINT []
SHELL ["bash", "-c"]

# The purpose of the health check is to notify the dependent
# containers to start only after the certificate is generated,
# or the existing certificate is still valid.
# Rerunning the health check should be avoided to keep the CPU
# usage low. The `timeout` cannot be disabled.
HEALTHCHECK --interval=1s --timeout=9000000300s --retries=0 \
    CMD while true; do \
            if [ ! -f /dev/shm/exited ]; then \
                if [ -f /dev/shm/exit-code ]; then \
                    touch /dev/shm/exited; \
                    exit $(< /dev/shm/exit-code); \
                fi; \
                sleep 0.1; \
                continue; \
            fi; \
            rm /dev/shm/exited; \
            sleep 9000000000; \
            exit; \
        done

CMD trap 'exit' TERM INT; \
    exit_code=/dev/shm/exit-code; \
    last_renewal=/tmp/certbot/last-renewal; \
    certificate=/etc/letsencrypt/live/$DOMAIN/fullchain.pem; \
    install -d -m 0755 /tmp/certbot/{lib,log}; \
    rm -f $last_renewal &>/dev/null; \
    sudo chmod 755 /etc/letsencrypt; \
    sudo chown -R certbot:certbot /etc/letsencrypt; \

    # Certificate expiration date in RFC 2822 format
    expiration_date() { \
        date=$(openssl x509 -noout -enddate -in $certificate); \
        echo $date | awk -v FS='(=| GMT)' '{print $2}'; \
    }; \

    # Ignoring invalid SNIs which is not part of the parent domain
    domains="$DOMAIN,www.$DOMAIN"; \
    for sni in 'XRAY_SNI' 'XRAY_CDN_SNI' 'OCSERV_SNI'; do \
        if [[ ${!sni} =~ "$DOMAIN"$ ]]; then \
            domains+=",${!sni}"; \
        fi; \
    done; \

    renew=$( \
        [ ! -z $CERTBOT_RENEWAL_LEFT_DAYS ] && \
        (( $CERTBOT_RENEWAL_LEFT_DAYS > 0 && $CERTBOT_RENEWAL_LEFT_DAYS < 90 )) && \
        echo true || \
        echo false \
    ); \
    if [ $renew = false ]; then \
        echo "Certificate auto renewal is disabled"; \
    fi; \

    delay=false; \
    sleep=3600; \
    while true; do \
        if [ $delay = true ]; then \
            sleep $sleep & wait $!; \
        else \
            delay=true; \
        fi; \

        if [ -f $certificate ]; then \
            regenerate=false; \
            subjects=($( \
                openssl x509 -noout -in $certificate -ext subjectAltName \
                | grep DNS \
                | sed 's/[DNS:|,]//g' \
                | xargs \
            )); \

            if [[ ! " ${subjects[*]} " =~ " *.$DOMAIN " ]]; then \
                if [[ $ENABLE_CERTBOT_HTTP_MODE == true ]]; then \
                    # Searching for changed SNI values since
                    # the non-wildcard certificate was issued
                    for domain in ${domains//,/ }; do \
                        if [[ ! " ${subjects[*]} " =~ " ${domain} " ]]; then \
                            regenerate=true; \
                            echo "One of the SNI values has been changed" \
                                "and the certificate needs to be regenerated"; \
                            break; \
                        fi; \
                    done; \
                else \
                    echo "The previously issued certificate is not a wildcard" \
                        "certificate and the certificate needs to be regenerated"; \
                    regenerate=true; \
                fi; \
            fi; \

            if [ $regenerate = false ]; then \
                if [ $renew = false ]; then \
                    # Just keep the container running
                    sleep=infinity; \
                    [ ! -f $last_renewal ] && echo $(date '+%s' -d "$(expiration_date)") > $last_renewal; \
                    echo 0 > $exit_code; \
                    continue; \
                elif openssl x509 \
                    -noout \
                    -checkend $(( 3600 * 24 * $CERTBOT_RENEWAL_LEFT_DAYS )) \
                    -in $certificate &>/dev/null; \
                then \
                    date=$(expiration_date); \
                    echo "Certificate is valid and will expire at $(date -Iseconds -d "$date")"; \
                    [ ! -f $last_renewal ] && echo $(date '+%s' -d "$date") > $last_renewal; \
                    echo 0 > $exit_code; \
                    continue; \
                elif ! openssl x509 -noout -checkend 0 -in $certificate &>/dev/null; then \
                    echo "Certificate is expired"; \
                else \
                    echo "Certificate will expire in less than $CERTBOT_RENEWAL_LEFT_DAYS days"; \
                fi; \
            fi; \
        fi; \

        code=0; \
        message="Getting a new certificate..."; \
        if [[ $ENABLE_CERTBOT_HTTP_MODE == true ]]; then \
            echo $message; \
            certbot certonly \
                --non-interactive \
                --agree-tos \
                --force-renewal \
                --standalone \
                --preferred-challenges http \
                --work-dir /tmp/certbot/lib \
                --logs-dir /tmp/certbot/log \
                --email $EMAIL \
                --cert-name $DOMAIN \
                --domain $domains; \

            code=$?; \
        elif [[ $ENABLE_AUTHORITATIVE_ZONE == true ]]; then \
            config=/dev/shm/rfc2136.ini; \
            echo "dns_rfc2136_server = $BIND_IPV4" > $config; \
            echo "dns_rfc2136_port = 53" >> $config; \
            echo "dns_rfc2136_name = certbot" >> $config; \
            echo "dns_rfc2136_algorithm = HMAC-SHA512" >> $config; \
            echo -n "dns_rfc2136_secret = " >> $config; \
            echo $(sudo cat /tmp/bind/session.key | sed -rn 's/\s+secret\s+\"(.*)\";/\1/p') >> $config; \
            chmod 600 $config; \
            echo $message; \

            certbot certonly \
                --non-interactive \
                --agree-tos \
                --force-renewal \
                --dns-rfc2136 \
                --dns-rfc2136-propagation-seconds 10 \
                --dns-rfc2136-credentials $config \
                --work-dir /tmp/certbot/lib \
                --logs-dir /tmp/certbot/log \
                --email $EMAIL \
                --cert-name $DOMAIN \
                --domain "$DOMAIN,*.$DOMAIN"; \

            code=$?; \
            rm -f $config; \
        elif [ ! -z "$CLOUDFLARE_API_TOKEN" ]; then \
            config=/dev/shm/cloudflare.ini; \
            echo "dns_cloudflare_api_token = $CLOUDFLARE_API_TOKEN" > $config; \
            chmod 600 $config; \
            echo $message; \

            certbot certonly \
                --non-interactive \
                --agree-tos \
                --force-renewal \
                --dns-cloudflare \
                --dns-cloudflare-propagation-seconds 30 \
                --dns-cloudflare-credentials $config \
                --work-dir /tmp/certbot/lib \
                --logs-dir /tmp/certbot/log \
                --email $EMAIL \
                --cert-name $DOMAIN \
                --domain "$DOMAIN,*.$DOMAIN"; \

            code=$?; \
            rm -f $config; \
        elif [ ! -f $certificate ]; then \
            echo "The TLS certificate does not exist" \
                "and no method has enabled to generate one" >&2; \
            code=2; \
        fi; \

        if [ $code = 0 ]; then \
            sleep=3600; \
            echo $(date '+%s' -d "$(expiration_date)") > $last_renewal; \
            chmod -R u+rwX,go+rX,go-w /etc/letsencrypt/{live,archive}/$DOMAIN; \
            rm -r /tmp/certbot/log/*; \
        elif [ ! -f $exit_code ]; then \
            # Reporting the error on failure for the first try
            exit $code; \
        else \
            # Retrying faster on failure
            sleep=300; \
        fi; \

        find /etc/letsencrypt -type d -empty -delete; \
        echo $code > $exit_code; \

    done
