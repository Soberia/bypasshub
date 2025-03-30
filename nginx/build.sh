#!/usr/bin/env sh

set -e

wget http://nginx.org/download/nginx-$NGINX_VERSION.tar.gz
tar xf nginx-$NGINX_VERSION.tar.gz
cd nginx-$NGINX_VERSION

git clone --depth 1 https://github.com/tokers/zstd-nginx-module.git
git clone --recurse-submodules -j8 --depth 1 https://github.com/google/ngx_brotli.git

mkdir ngx_brotli/deps/brotli/out
cd ngx_brotli/deps/brotli/out

flags="-Ofast -m64 -march=native -mtune=native -flto -funroll-loops -ffunction-sections -fdata-sections -Wl,--gc-sections"
cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS="$flags" -DCMAKE_CXX_FLAGS="$flags" -DCMAKE_INSTALL_PREFIX=./installed ..
cmake --build . --config Release --target brotlienc

cd ../../../..
./configure --with-compat --add-dynamic-module=zstd-nginx-module --add-dynamic-module=ngx_brotli
make modules
