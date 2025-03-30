#!/usr/bin/env sh

set -e

wget https://www.infradead.org/ocserv/download/ocserv-$VERSION.tar.xz
tar xf ocserv-$VERSION.tar.xz
cd ocserv-$VERSION

autoreconf -fvi
./configure \
    --disable-systemd \
    --disable-compression \
    --without-root-tests \
    --without-asan-broken-tests \
    --without-tun-tests \
    --without-llhttp \
    --without-protobuf \
    --without-maxmind \
    --without-geoip \
    --without-liboath \
    --without-pam \
    --without-radius \
    --without-gssapi \
    --without-pcl-lib \
    --without-utmp \
    --without-libwrap \
    --without-lz4 \
    --with-local-talloc \
    --with-pager=""

make
make install
