FROM ubuntu:rolling
LABEL org.opencontainers.image.title=BIND
RUN apt-get update && \
    apt-get install -y --no-install-recommends bind9 bind9utils dnsutils iptables && \
    apt-get clean; \
    #
    ln -s /tmp/bind /run/named;

USER bind
COPY --chmod=655 *.sh /usr/local/sbin/
ENTRYPOINT ["entrypoint.sh"]
