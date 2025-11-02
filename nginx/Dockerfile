ARG NGINX_VERSION=1.29.3

FROM nginx:$NGINX_VERSION AS modules
ARG NGINX_VERSION
COPY --chmod=655 build.sh /usr/local/sbin/
RUN apt-get update && \
    apt-get install -y wget git make cmake gcc zlib1g-dev libpcre2-dev libzstd-dev; \
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
