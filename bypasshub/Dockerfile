ARG PYTHON_VERSION=3.12
ARG XRAY_VERSION=1.8.13

FROM python:$PYTHON_VERSION-slim AS packages
ARG PYTHON_VERSION
ARG XRAY_VERSION
COPY . /usr/local/src/bypasshub/bypasshub/
COPY --chmod=655 build.sh /usr/local/sbin/
RUN apt-get update && apt-get install -y wget; \
    build.sh;

FROM python:$PYTHON_VERSION-slim
LABEL org.opencontainers.image.title=BypassHub
COPY --from=packages /usr/local/lib/ /usr/local/lib/
COPY --from=packages /usr/local/bin/bypasshub /usr/local/bin/bypasshub
RUN useradd --create-home --gid www-data bypasshub

USER bypasshub
ENTRYPOINT ["python", "-m", "bypasshub"]
