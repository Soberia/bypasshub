#!/usr/bin/env sh

if [ "$ENABLE_IPV6" = true ]; then
    # Configuring the NDP Proxy for the downstream clients
    ip -6 neighbour $([ "$REASON" = "connect" ] && echo add || echo del) \
        proxy $IPV6_REMOTE dev eth0
    exit $?
fi

exit 0
