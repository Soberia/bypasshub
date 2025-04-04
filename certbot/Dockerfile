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
    echo -n 'certbot ALL=(root) NOPASSWD:/bin/cat /tmp/bind/session.key' >> /etc/sudoers;

USER certbot
COPY --chmod=655 *.sh /usr/local/sbin/

# The purpose of the health check is to notify the dependent
# containers to start only after the certificate is generated,
# or the existing certificate is still valid.
# Rerunning the health check should be avoided to keep the CPU
# usage low. The `timeout` cannot be disabled.
HEALTHCHECK --interval=1s --timeout=9000000300s --retries=0 \
    CMD healthcheck.sh

ENTRYPOINT ["entrypoint.sh"]
