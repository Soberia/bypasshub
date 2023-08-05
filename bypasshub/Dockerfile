FROM python:slim AS packages
COPY . /usr/local/src/bypasshub/
RUN apt-get update && \
    apt-get install -y git; \
    pip install --no-cache-dir --editable /usr/local/src/bypasshub/; \
    pip install --no-cache-dir poetry; \
    #
    grpc_version=$(grep -oP 'grpcio.=\K.*\d' /usr/local/src/bypasshub/pyproject.toml); \
    git clone --depth 1 https://github.com/laoshan-tech/xray-rpc.git; \
    cd xray-rpc; \
    sed -r 's/(grpcio.*)".*"/\1"^$grpc_version"/g' pyproject.toml; \
    poetry lock; \
    poetry install; \
    poetry run python compile.py; \
    pip install .; \
    pip uninstall --yes poetry poetry-core;

FROM python:slim
COPY --from=packages /usr/local/lib/ /usr/local/lib/
COPY --from=packages /usr/local/bin/bypasshub /usr/local/bin/bypasshub
RUN useradd --create-home --gid www-data bypasshub

USER bypasshub
ENTRYPOINT ["python", "-m", "bypasshub"]
