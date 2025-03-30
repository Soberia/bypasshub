ARG VERSION=1.3.0

FROM ubuntu:rolling AS ocserv
ARG VERSION
COPY --chmod=655 build.sh /usr/local/sbin/
RUN apt-get update && \
    apt-get install -y wget xz-utils make gcc pkg-config autoconf automake \
        ipcalc-ng nettle-dev libgnutls30 libgnutls28-dev libev-dev \
        libseccomp-dev libreadline-dev libnl-route-3-dev; \
    build.sh;

FROM ubuntu:rolling
LABEL org.opencontainers.image.title=OpenConnect
COPY --from=ocserv /usr/local/bin/ /usr/local/bin/
COPY --from=ocserv /usr/local/sbin/ocserv* /usr/local/sbin/
RUN apt-get update && \
    apt-get install -y --no-install-recommends iptables iproute2 socat \
        gnutls-bin libgnutls28-dev libev-dev libseccomp-dev \
        libreadline-dev libnl-route-3-dev && \
    apt-get clean; \
    #
    useradd --system --user-group --no-create-home --home-dir /tmp/ocserv \
        --shell /usr/sbin/nologin --uid 102 ocserv;

COPY --chmod=655 *.sh /usr/local/sbin/
ENTRYPOINT ["entrypoint.sh"]
