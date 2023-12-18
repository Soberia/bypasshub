FROM certbot/certbot
LABEL org.opencontainers.image.title=Certbot
RUN apk add --no-cache bash

ENTRYPOINT [ ]
SHELL ["bash", "-c"]
CMD \
    # Ignoring invalid SNIs which is not part of the parent domain
    domains="$DOMAIN,www.$DOMAIN"; \
    for sni in 'XRAY_SNI' 'XRAY_CDN_SNI' 'OCSERV_SNI'; do \
        if [[ ${!sni} =~ "$DOMAIN"$ ]]; then \
            domains+=",${!sni}"; \
        fi; \
    done; \

    if certbot certonly \
        --non-interactive \
        --agree-tos \
        --standalone \
        --preferred-challenges http \
        --email $EMAIL \
        --domain $domains; \
    then \
        chmod -R u+rwX,go+rX,go-w /etc/letsencrypt/{live,archive}/$DOMAIN; \
    fi; \

    find /etc/letsencrypt -type d -empty -delete
