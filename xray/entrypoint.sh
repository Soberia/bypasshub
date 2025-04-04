#!/usr/bin/env bash

trap 'exit' TERM INT

install -d -g users -m 0750 /tmp/xray
rm -f /tmp/xray/*.sock &>/dev/null
ln -s /dev/shm/xray.json /tmp/xray/xray.json &>/dev/null
cp -f /usr/local/etc/xray/xray.json /dev/shm/xray.json
[[ $ENABLE_XRAY_SUBSCRIPTION == true ]] &&
    cp -f /usr/local/etc/xray/confs/cdn-ips /tmp/xray/cdn-ips 2>/dev/null

# Injecting the environment variables
sed -i "s|\$DOMAIN\b|$DOMAIN|g" /dev/shm/xray.json

# Waiting for the users list to be generated
current_time=$(date '+%s')
for (( timeout=50; timeout > 0; timeout-- )); do
    [ -s /tmp/bypasshub/last-generate ] &&
        (( $(< /tmp/bypasshub/last-generate) >= $current_time )) &&
        break
    sleep 0.1
done

# Injecting the users
readarray -t users < /tmp/bypasshub/users
if [ ! -z "${users}" ]; then
    clients_tcp=""
    clients_ws=""
    for user in "${users[@]}"; do
        user=($user)
        shared="\"email\":\"${user[0]}@$DOMAIN\",\"id\":\"${user[1]}\""
        clients_tcp+="{\"flow\":\"xtls-rprx-vision\",$shared},"
        if [[ $ENABLE_XRAY_CDN == true ]]; then
            clients_ws+="{\"flow\":null,$shared},"
        fi
    done

    [[ $ENABLE_XRAY_CDN != true ]] && clients_ws=','
    json=$(
        jq -c \
        ".inbounds[1].settings.clients += [${clients_tcp::-1}] | \
        .inbounds[2].settings.clients += [${clients_ws::-1}]" \
        /dev/shm/xray.json
    )
    echo -E "$json" > /dev/shm/xray.json
    unset users user shared json clients_tcp clients_ws
fi

# There is no way to reload the certificate manually.
# The `Xray-core` periodically reloads the certificate
# if the certificate has been modified. 

exec /usr/local/bin/xray run \
    -config /tmp/xray/xray.json \
    -confdir /usr/local/etc/xray/confs
