ARG NGINX_VERSION=1.27.4

# Zstandard module will not get compiled with default NGINX image based on Debian.
# See https://github.com/tokers/zstd-nginx-module/issues/37
FROM ubuntu:22.04 AS modules
ARG NGINX_VERSION
COPY --chmod=655 build.sh /usr/local/sbin/
RUN apt-get update && \
    apt-get install -y wget git make cmake gcc libpcre3-dev zlib1g-dev libzstd-dev; \
    build.sh;

FROM nginx:$NGINX_VERSION
LABEL org.opencontainers.image.title=NGINX
COPY --chmod=644 --from=modules /nginx*/objs/*.so /usr/lib/nginx/modules/
RUN apt-get update && \
    apt-get install -y --no-install-recommends iptables libcap2-bin; \
    apt-get clean; \
    # Adding the required kernel capability for the NGINX binary file for
    # `proxy_bind transparent` directive to work correctly without running
    # the process as the root user.
    # See https://github.com/nginxinc/docker-nginx-unprivileged/issues/177
    setcap cap_net_raw=pe /usr/sbin/nginx;

USER nginx
COPY --chmod=655 *.sh /usr/local/sbin/
ENTRYPOINT ["entrypoint.sh"]
