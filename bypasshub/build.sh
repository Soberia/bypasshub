#!/usr/bin/env bash

set -e
shopt -s globstar

wget https://github.com/XTLS/Xray-core/archive/refs/tags/v$XRAY_VERSION.tar.gz
tar xf v$XRAY_VERSION.tar.gz

package=xray_rpc
mkdir $package
pip install --no-cache-dir --editable /usr/local/src/bypasshub/bypasshub/
python -m grpc_tools.protoc \
    --python_out $package \
    --grpc_python_out $package \
    --proto_path Xray-core-$XRAY_VERSION \
    Xray-core-$XRAY_VERSION/**/*.proto

# The `protobuf` doesn't support relative imports in generated modules.
# Therefor, relative import statements should be replaced with absolute import.
# See https://github.com/protocolbuffers/protobuf/issues/1491
sed -i -E \
    -e "s/(from\s+)(.*)(pb2)$/\1$package.\2\3/g" \
    -e "s/(importlib.import_module\(')(.*)('\))/\1$package.\2\3/g" \
    $package/**/*.py

cat > pyproject.toml <<EOF
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = '$package'
version = '$XRAY_VERSION'

[tool.setuptools]
packages = ['$package']
EOF

pip install .
mv $package /usr/local/lib/python*/site-packages
