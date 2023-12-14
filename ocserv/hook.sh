#!/usr/bin/env bash

if [[ $ENABLE_IPV6 != true ]]; then
    exit 0
fi

# Configuring the NDP Proxy for the downstream clients
ip -6 neighbour $([[ $REASON == "connect" ]] && echo add || echo del) \
    proxy $IPV6_REMOTE dev eth0
