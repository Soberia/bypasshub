ARG VERSION=1.8.13

FROM ubuntu:rolling AS xray
ARG VERSION
RUN apt-get update && \
    apt-get install -y curl unzip; \
    curl -sSL -o archive.zip \
        "https://github.com/XTLS/Xray-core/releases/download/v$VERSION/Xray-linux-64.zip"; \
    unzip archive.zip;

FROM ubuntu:rolling
LABEL org.opencontainers.image.title=Xray-core
COPY --from=xray --chmod=755 /xray /usr/local/bin/xray
COPY --from=xray --chmod=644 /geo*.dat /usr/local/share/xray/
RUN apt-get update && \
    apt-get install -y --no-install-recommends jq iptables; \
    apt-get clean; \
    #
    useradd --gid proxy xray;

USER xray
COPY --chmod=655 *.sh /usr/local/sbin/
ENTRYPOINT ["entrypoint.sh"]
