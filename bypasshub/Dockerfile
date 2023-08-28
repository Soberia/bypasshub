ARG XRAY_VERSION=1.8.3

FROM python:slim AS packages
ARG XRAY_VERSION
COPY . /usr/local/src/bypasshub/
SHELL ["bash", "-c"]
RUN apt-get update && \
    apt-get install -y wget; \
    #
    wget https://github.com/XTLS/Xray-core/archive/refs/tags/v$XRAY_VERSION.tar.gz; \
    tar xf v$XRAY_VERSION.tar.gz; \
    #
    package=xray_rpc; \
    mkdir $package; \
    shopt -s globstar; \
    pip install --no-cache-dir --editable /usr/local/src/bypasshub/; \
    python -m grpc_tools.protoc \
        --python_out $package \
        --grpc_python_out $package \
        --proto_path Xray-core-$XRAY_VERSION \
        Xray-core-$XRAY_VERSION/**/*.proto; \
    # The `protobuf` doesn't support relative imports in generated modules.
    # Therefor, relative import statements should be replaced with absoule import.
    # See https://github.com/protocolbuffers/protobuf/issues/1491
    sed -i -E \
        -e "s/(from\s+)(.*)(pb2)$/\1$package.\2\3/g" \
        -e "s/(importlib.import_module\(')(.*)('\))/\1$package.\2\3/g" \
        $package/**/*.py; \
    #
    echo '[build-system]' > pyproject.toml; \
    echo 'requires = ["setuptools"]' >> pyproject.toml; \
    echo 'build-backend = "setuptools.build_meta"' >> pyproject.toml; \
    echo '[project]' >> pyproject.toml; \
    echo "name = '$package'" >> pyproject.toml; \
    echo "version = '$XRAY_VERSION'" >> pyproject.toml; \
    echo '[tool.setuptools]' >> pyproject.toml; \
    echo "packages = ['$package']" >> pyproject.toml; \
    pip install .; \
    mv $package /usr/local/lib/python*/site-packages;

FROM python:slim
COPY --from=packages /usr/local/lib/ /usr/local/lib/
COPY --from=packages /usr/local/bin/bypasshub /usr/local/bin/bypasshub
RUN useradd --create-home --gid www-data bypasshub

USER bypasshub
ENTRYPOINT ["python", "-m", "bypasshub"]
