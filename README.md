# 💡 **About**

`bypasshub` is an abstraction around the set of tools to bypass internet censorship in extremely restricted regions such as Iran or China.

The goal of the project is to minimize the work needed to configure required stuff to get things done for the end user.
It's also tried to follow the best practices to honor both security and performance.

# ⚙️ **How It Works**

```
                                         ____________ 
                                        | Xray-core  |
                         -------------> |Proxy Server| ---------------
                        ¦               |____________|                ¦
                        ¦                     ¦                       ¦
                        ¦                     ¦                       ¦
                        ¦                     ˅                       ˅
                     _______              __________              __________
                    |       |            |   BIND   |            |          |
 Client ----------> | NGINX | ---------> |DNS Server|            | Internet |
                    |_______|            |__________|            |__________|
                        ¦                     ˄                       ˄
                        ¦                     ¦                       ¦
                        ¦                     ¦                       ¦
                        ¦                ____________                 ¦
                        ¦               | OpenConnect|                ¦
                         -------------> | VPN Server |----------------
                                        |____________|
```

`bypasshub` just consists of a bunch of `Docker` containers.

`NGINX` role is an entry point for all the incoming connections. From there, the incoming connection gets redirected to its destination based on the destination port. For TLS-based connections on TCP ports, the connection is routed based on specified [SNI](https://en.wikipedia.org/wiki/Server_Name_Indication) value and if there is no match, a dummy webpage will be returned instead to mimic a real web server's behavior when confronted with national firewall active probing.

Currently, `Xray-core` proxy and `OpenConnect` VPN servers are available. The clients of these services are isolated and can't communicate with each other or with other containers on the network with an exception for sending the DNS queries to the `BIND` caching DNS server.

All of the containers run as a non-privileged user except the `OpenConnect`.

# 📋 **How to Use**

Make sure you've installed the [`Docker`](https://docs.docker.com/engine/install/) with [`Compose CLI`](https://docs.docker.com/compose/reference/) V2 support. Then, clone the repository and build the services:

```bash
git clone https://github.com/Soberia/bypasshub.git
cd bypasshub && docker compose build
```

Fill the following parameters in the [config file](#-configuration) with your information:

- [`DOMAIN`](#DOMAIN)
- [`PUBLIC_IPV4`](#PUBLIC_IPV4)

> **Note**  
> It's also recommended to change [`XRAY_SNI`](#XRAY_SNI), [`XRAY_CDN_SNI`](#XRAY_CDN_SNI) and [`OCSERV_SNI`](#OCSERV_SNI) subdomain part to something else. For example, default [`XRAY_SNI`](#XRAY_SNI) value is `xr.$DOMAIN`, you can change it to `hotdog.$DOMAIN` or any other random value instead. You'll use these values when connecting from the client side.

You need to go to your domain registrar and set the nameservers to the `ns1.$DOMAIN` and `ns2.$DOMAIN` (replace `$DOMAIN` with your actual domain, e.g. `ns1.domain.com`). You also need to create glue records for these nameservers you just defined. The glue records for your nameservers should point to your server's public IP address. (i.e. `ns1.$DOMAIN -> $PUBLIC_IPV4`)

However, if you already have a DNS server on your machine or you use your DNS registrar's, you can skip the above step and enable [`ENABLE_CERTBOT_HTTP_MODE`](#ENABLE_CERTBOT_HTTP_MODE) and disable [`ENABLE_AUTHORITATIVE_ZONE`](#ENABLE_AUTHORITATIVE_ZONE) parameters because you can't use two DNS servers at the same time on a same port. On your DNS server, create an `A` (and/or `AAAA`) record for [`DOMAIN`](#DOMAIN), [`XRAY_SNI`](#XRAY_SNI), [`XRAY_CDN_SNI`](#XRAY_CDN_SNI), [`OCSERV_SNI`](#OCSERV_SNI) and `www.$DOMAIN` and point them to the [`PUBLIC_IPV4`](#PUBLIC_IPV4) (or [`NGINX_IPV6`](#NGINX_IPV6)).

> **Note**  
> If you use the Cloudflare DNS server, you can go to the **My Profile > API Tokens** of your dashboard and create a new API token for editing the DNS zone and specify your token with the [`CLOUDFLARE_API_TOKEN`](#CLOUDFLARE_API_TOKEN) parameter. In this way, a wildcard TLS certificate will be generated instead and there is no need to regenerate the certificate again when the SNI values have been changed.  
> Both [`ENABLE_AUTHORITATIVE_ZONE`](#ENABLE_AUTHORITATIVE_ZONE) and [`ENABLE_CERTBOT_HTTP_MODE`](#ENABLE_CERTBOT_HTTP_MODE) parameters should be disabled for this to take effect.

> **Warning**  
> You need to stop any service that you might have listening on the TCP port `80` if the [`ENABLE_CERTBOT_HTTP_MODE`](#ENABLE_CERTBOT_HTTP_MODE) parameter is enabled.

> **Warning**  
> You may need some time for your nameservers to get populated before you continue.

Now, bring the containers up:

```bash
docker compose up -d
```

## Managing Users

See the [user management](bypasshub/README.md) page.

## Connecting from Client

Get the [`Xray-core`](https://github.com/XTLS/Xray-core) and [`OpenConnect`](https://gitlab.com/openconnect/openconnect) clients for your devices.

- For `Xray-core`, in your client, add a subscription with the following URL with the user's credentials:

    ```
    https://$DOMAIN:$TLS_PORT/subscription?username=USERNAME&uuid=PASSWORD
    ```

    <details>
    <summary style="color: cyan">Adding the Server Manually</summary>

    Use these values when adding a new server in your client:

    ```
    Protocol: VLESS
    Address: $XRAY_SNI
    Port: $TLS_PORT
    UUID: PASSWORD
    Flow: xtls-rprx-vision
    Transport Protocol: TCP
    Security: TLS
    ```

    or if you [want to connect via the CDN](#using-a-cdn):

    ```
    Protocol: VLESS
    Address: $XRAY_CDN_SNI (or IP addresses of your CDN provider)
    Port: $CDN_TLS_PORT
    UUID: PASSWORD
    Transport Protocol: WS
    Transport Host: $XRAY_CDN_SNI
    Transport Path: /ws?ed=2560
    Security: TLS
    SNI: $XRAY_CDN_SNI
    ```

    <details>
    <summary style="color: cyan">Using IP Address Instead of Domain</summary>

    If your domain already is blocked, change [`XRAY_SNI`](#XRAY_SNI) parameter's value to something else (e.g. `google.com`) and rebuild the containers and change the following values to connect with the IP address instead: (replace [`PUBLIC_IPV4`](#PUBLIC_IPV4) with [`NGINX_IPV6`](#NGINX_IPV6) if you want to use IPv6)

    ```
    Address: $PUBLIC_IPV4
    SNI: $XRAY_SNI
    ```

    You may also need to tell your client to allow insecure connections.
    </details>
    </details>


- For `OpenConnect`, you can connect to the server with the following command: (here's on Windows client)

    ```cmd
    echo PASSWORD| openconnect.exe ^
        --non-inter ^
        --passwd-on-stdin ^
        --interface wintun ^
        --user USERNAME ^
        --server $OCSERV_SNI:$TLS_PORT
    ```

    If you're unable to establish a successful DTLS connection, you can append the `--no-dtls` argument for a faster initial connection.

    > **Note**  
    > If [`OCSERV_KEY`](#OCSERV_KEY) parameter is set, `--server` argument should contain the secret key as a query string:
    > 
    > ```cmd
    > --server $OCSERV_SNI:$TLS_PORT/?$OCSERV_KEY
    > ```

    <details>
    <summary style="color: cyan">Using IP Address Instead of Domain</summary>

    If your domain already is blocked, change [`OCSERV_SNI`](#OCSERV_SNI) parameter's value to something else (e.g. `bing.com`) and rebuild the containers and append the following arguments to connect with the IP address instead: (replace [`PUBLIC_IPV4`](#PUBLIC_IPV4) with [`NGINX_IPV6`](#NGINX_IPV6) if you want to use IPv6)

    ```cmd
        --sni $OCSERV_SNI ^
        --resolve $OCSERV_SNI:$PUBLIC_IPV4
    ```

    After reconnecting with added arguments, you also need to add the printed fingerprint token as the `--servercert` argument:

    ```cmd
        --servercert pin-sha256:Q8CaEEFJqy2xyD9+SsAwfMuVH7jz/Rq0r/HXmNkIg9k=
    ```
    </details>

## Using a CDN

If your server's IP address (or certain ports) is blocked or traffic to your server gets throttled by the national firewall, you might be able to access your server again or improve the connection speed by placing your server behind a CDN. However, only `Xray-core` can benefit from this due to the fact that usually the CDN providers don't offer tunnel at the TCP/UDP level on their free plans. The `Xray-core` is able to work on a `WebSocket` or `gPRC` connection and a CDN provider like Cloudflare supports both of these protocols for free.

The following will demonstrate how to place your server behind the Cloudflare CDN, but the instructions should be the same for other providers:
- Login to your [dashboard](https://dash.cloudflare.com).
- Add your website and if your current DNS records couldn't be detected correctly, from the **DNS** panel, create an `A` (and/or `AAAA`) record for [`DOMAIN`](#DOMAIN), [`XRAY_SNI`](#XRAY_SNI), [`XRAY_CDN_SNI`](#XRAY_CDN_SNI), [`OCSERV_SNI`](#OCSERV_SNI) and `www.$DOMAIN` and point them to the [`PUBLIC_IPV4`](#PUBLIC_IPV4) (or [`NGINX_IPV6`](#NGINX_IPV6)). The **Proxy status** should be enabled for all except for the [`XRAY_SNI`](#XRAY_SNI) and [`OCSERV_SNI`](#OCSERV_SNI). You'll need to swap your nameservers to the Cloudflare's in your domain registrar and also remove the glue records.
- From the **SSL/TLS** panel, change the encryption mode to **Full** or **Full (strict)**. In the **Edge Certificates** section, enable the **TLS 1.3** option and set the **Minimum TLS Version** option to the **TLS 1.3**.
- In the **Network** panel, make sure the **WebSockets** is enabled.
- If the [`ENABLE_XRAY_SUBSCRIPTION`](#ENABLE_XRAY_SUBSCRIPTION) parameter is enabled, you should set the **Caching Level** option to the **No query string** in the **Configuration** section of **Caching** panel.
- The [`ENABLE_AUTHORITATIVE_ZONE`](#ENABLE_AUTHORITATIVE_ZONE) and [`ENABLE_XRAY_CDN`](#ENABLE_XRAY_CDN) parameters should be disabled and enabled respectively. Rebuild the containers after the modification.
- [Update](#connecting-from-client) your `Xray-core` client configurations to reflect the changes. If you can't make a successful connection, try with an [IP scanner](https://cloudflare-v2ray.vercel.app) to find healthy IP addresses. You can also put these IP addresses that work on different ISPs to the `.data/xray/configs/cdn-ips` to publish them on the subscription:
    ```
    1.1.1.1 ISP#1
    1.1.1.2 ISP#2
    ```
- (Optional) Now, you're able to connect to the server either with the CDN or directly. But if you only need to connect via the CDN, you might want to remove the DNS records for the [`XRAY_SNI`](#XRAY_SNI) and [`OCSERV_SNI`](#OCSERV_SNI) to hide your server's IP address from the national firewall.

## Dummy Website

The TLS-based services like `Xray-core` and `OpenConnect` are camouflaged behind a web server which decides the destination of incoming traffic based on the passed SNI value.

By default, for invalid requests (or authentication failures in the case of `Xray-core`) an empty `index.html` template located in `.data/nginx/static` directory will be returned. You should modify it up to the point to represent a good unique indistinguishable fake webpage. If you need to include static assist like `JavaScript`, `CSS` or images, you can place them in the same mentioned directory.

> **Warning**  
> `OpenConnect` VPN server [can be detected through the exposed SNI](https://gitlab.com/openconnect/ocserv/-/issues/393). It's also recommended to set [`OCSERV_KEY`](#OCSERV_KEY) parameter to hide the server identity.

## Additional Configurations

For `Xray-core` you can place [additional configuration](https://xtls.github.io/Xray-docs-next/config/features/multiple.html) files in the `.data/xray/configs` directory (e.g. to block BitTorrent traffic).

For `OpenConnect`, you can place [user-based configuration](http://ocserv.gitlab.io/www/manual.html) files in the `.data/ocserv/configs` directory (e.g. to give the user a static IP address). The name of the config file should correspond to the defined username.

## DNSSEC

For [securing the exchanged data](https://en.wikipedia.org/wiki/Domain_Name_System_Security_Extensions) for your authoritative DNS zone, you can enable the [`ENABLE_DNSSEC`](#ENABLE_DNSSEC) parameter ([`ENABLE_AUTHORITATIVE_ZONE`](#ENABLE_AUTHORITATIVE_ZONE) also should be enabled) and restart the container to generate the keys:

```bash
docker compose restart bind --no-deps
```

and get the keys by running the following command and setting them on your parent domain through your domain registrar:

```bash
docker compose exec bind \
    bash -c "dig @localhost dnskey $DOMAIN | dnssec-dsfromkey -Af - $DOMAIN"
```

## IPv6

Enable the [`ENABLE_IPV6`](#ENABLE_IPV6) parameter and you can either specify your server's Global Unicast IPv6 address prefix with [`IPV6_PREFIX`](#IPV6_PREFIX) parameter or fill the rest of IPv6 parameters manually.

You may also need the following firewall rules in the `FORWARD` chain: (they won't be permanent)

```bash
ip6tables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT # Only needed if doesn't already exist
ip6tables -A FORWARD -p ipv6-icmp -j ACCEPT # Only needed if doesn't already exist
ip6tables -A FORWARD -d $IPV6_SUBNET -j ACCEPT
ip6tables -A FORWARD -s $IPV6_SUBNET -o eth0 -j ACCEPT
```

## Logs

The persistence of the logs can be controlled by the [`NGINX_LOG_PURGE_INTERVAL`](#NGINX_LOG_PURGE_INTERVAL) parameter.  
You can see the logs by running the following commands:

```bash
docker compose exec nginx cat /var/log/nginx/access.log # Clients access log
docker compose exec nginx cat /var/log/nginx/static.log # Dummy website access log
docker compose exec nginx cat /var/log/nginx/api.log # API access log
docker compose exec nginx cat /var/log/nginx/error.log
```

## Update Containers

Stop and remove the current containers:

```bash
docker compose down --rmi all
```

Get the latest source:

```bash
git stash && \
    git pull && \
    git checkout stash -- .env && \
    git stash drop
```

then rebuild the containers:

```bash
docker compose build --no-cache && \
    docker compose up -d
```

## Uninstall

You can revoke the generated certificates if you don't need them anymore: (replace `revoke` with `delete` to only remove the certificates from the disk)

```bash
docker run --rm -it \
    -v $PWD/.data/certbot/letsencrypt:/etc/letsencrypt \
    certbot/certbot revoke --cert-name $DOMAIN
```

And to remove everything:

```bash
docker compose down --volumes --rmi all
```

# 🔧 **Configuration**

All the configurations take place in the `.env` file.
It's also possible to provide these parameters as environment variable which in this case they override the values in the config file.

> **Note**  
> All the parameters that start with `ENABLE_`, are switches. Their value evaluates to `true` if set to anything (including the empty value) or to `false` if the variable is commented out or removed entirely.

> **Note**  
> All the parameters that include `IPV6` in their name, will be ignored whenever [`ENABLE_IPV6`](#ENABLE_IPV6) is not enabled.

Variable                                                              | Type   | Description
--------------------------------------------------------------------- | :----: | -----------
<span id="ENABLE_XRAY">ENABLE_XRAY</span>                             | switch | Enables the `Xray-core` proxy server.
<span id="ENABLE_OCSERV">ENABLE_OCSERV</span>                         | switch | Enables the `OpenConnect` VPN server.
<span id="DOMAIN">DOMAIN</span>                                       | string | The domain to use for the web server and other TLS-based services.
<span id="XRAY_SNI">XRAY_SNI</span>                                   | string | The SNI value for routing traffic to the `Xray-core` proxy server.
<span id="XRAY_CDN_SNI">XRAY_CDN_SNI</span>                           | string | The SNI value for routing traffic to the `Xray-core` proxy server originated from the CDN.
<span id="OCSERV_SNI">OCSERV_SNI</span>                               | string | The SNI value for routing traffic to the `OpenConnect` VPN server.
<span id="EMAIL">EMAIL</span>                                         | string | The email address for registering the [Let's Encrypt](https://letsencrypt.org) TLS certificate. Certificate expiration reminders will be sent to this email address.
<span id="TLS_PORT">TLS_PORT</span>                                   | number | The TCP port for the web server and other TLS-based services.
<span id="CDN_TLS_PORT">CDN_TLS_PORT</span>                           | number | The TCP port for the TLS-based connections to the CDN. This value should only be changed when remapping the [`TLS_PORT`](#TLS_PORT) port on the CDN. (e.g. The connections on the CDN's port 443 would be forwarded to the server's port 8433)
<span id="OCSERV_DTLS_PORT">OCSERV_DTLS_PORT</span>                   | number | The UDP port for the `OpenConnect` VPN server's DTLS protocol.
<span id="ENABLE_AUTHORITATIVE_ZONE">ENABLE_AUTHORITATIVE_ZONE</span> | switch | Enables the authoritative DNS zone for provided [`DOMAIN`](#DOMAIN). The generated TLS certificate is a wildcard certificate when this parameter is enabled.
<span id="ENABLE_DNSSEC">ENABLE_DNSSEC</span>                         | switch | Enables the DNSSEC for the authoritative DNS zone.
<span id="DNS_CACHE_SIZE">DNS_CACHE_SIZE</span>                       | number | The DNS server's cache size in MB. The value of `0`, will dedicate all the available memory.
<span id="DNS_IPV4">DNS_IPV4</span>                                   | string | The IPv4 address for forwarding the DNS queries.
<span id="DNS_IPV6">DNS_IPV6</span>                                   | string | The IPv6 address for forwarding the DNS queries.
<span id="PUBLIC_IPV4">PUBLIC_IPV4</span>                             | string | The `Docker` host public IPv4 address. The provided [`DOMAIN`](#DOMAIN) will be resolved to this IPv4 address whenever [`ENABLE_AUTHORITATIVE_ZONE`](#ENABLE_AUTHORITATIVE_ZONE) is enabled.
<span id="OCSERV_IPV4_SUBNET">OCSERV_IPV4_SUBNET</span>               | string | The `OpenConnect` VPN server's IPv4 network address.
<span id="ENABLE_IPV6">ENABLE_IPV6</span>                             | switch | Enables the IPv6 for the containers.
<span id="IPV6_PREFIX">IPV6_PREFIX</span>                             | string | The `Docker` host Global Unicast IPv6 address prefix. This parameter can be used as a shorthand for other IPv6 parameters.
<span id="IPV6_SUBNET">IPV6_SUBNET</span>                             | string | The IPv6 network address for the containers. Network size should not be smaller than `/125`.
<span id="BYPASSHUB_IPV6">BYPASSHUB_IPV6</span>                       | string | The IPv6 address to allocate to the `BypassHub` container. This address must be in [`IPV6_SUBNET`](#IPV6_SUBNET) range.
<span id="BIND_IPV6">BIND_IPV6</span>                                 | string | The IPv6 address to allocate to the `BIND` container. This address must be in [`IPV6_SUBNET`](#IPV6_SUBNET) range.
<span id="CERTBOT_IPV6">CERTBOT_IPV6</span>                           | string | The IPv6 address to allocate to the `Certbot` container. This address must be in [`IPV6_SUBNET`](#IPV6_SUBNET) range.
<span id="NGINX_IPV6">NGINX_IPV6</span>                               | string | The IPv6 address to allocate to the `NGINX` container. This address must be in [`IPV6_SUBNET`](#IPV6_SUBNET) range. The provided [`DOMAIN`](#DOMAIN) will be resolved to this IPv6 address whenever [`ENABLE_AUTHORITATIVE_ZONE`](#ENABLE_AUTHORITATIVE_ZONE) is enabled.
<span id="XRAY_IPV6">XRAY_IPV6</span>                                 | string | The IPv6 address to allocate to the `Xray-core` container. This address must be in [`IPV6_SUBNET`](#IPV6_SUBNET) range.
<span id="OCSERV_IPV6">OCSERV_IPV6</span>                             | string | The IPv6 address to allocate to the `OpenConnect` container. This address must be in [`IPV6_SUBNET`](#IPV6_SUBNET) range.
<span id="OCSERV_IPV6_SUBNET">OCSERV_IPV6_SUBNET</span>               | string | The `OpenConnect` VPN server's IPv6 network address. This address must be in [`IPV6_SUBNET`](#IPV6_SUBNET) range.
<span id="OCSERV_CLIENTS_IPV6_CIDR">OCSERV_CLIENTS_IPV6_CIDR</span>   | number | The IPv6 network size that will be provided to the `OpenConnect` VPN server clients.
<span id="ENABLE_CERTBOT_HTTP_MODE">ENABLE_CERTBOT_HTTP_MODE</span>   | switch | Enables the `Certbot`'s `standalone` mode for generating the TLS certificate. The generated certificate is not a wildcard certificate and when the SNI values change, a new certificate will be generated as well and replace the old one.
<span id="ENABLE_XRAY_CDN">ENABLE_XRAY_CDN</span>                     | switch | Enables the `Xray-core` proxy server to work behind the CDN.
<span id="ENABLE_XRAY_SUBSCRIPTION">ENABLE_XRAY_SUBSCRIPTION</span>   | switch | Enables the `Xray-core` clients to access the configs by a subscription URL. Only authorized users have access to the subscription by providing their credentials.
<span id="NGINX_LOG_PURGE_INTERVAL">NGINX_LOG_PURGE_INTERVAL</span>   | number | The interval in seconds that `NGINX` logs would be cleared. The value of `0`, keeps the logs forever.
<span id="CERTBOT_RENEWAL_LEFT_DAYS">CERTBOT_RENEWAL_LEFT_DAYS</span> | number | The remained days until the TLS certificate expiration. The generated TLS certificate is valid for 90 days and it will renew automatically after the remained days to the expiration date specified by this parameter have crossed. The value of `0`, prevents the certificate regeneration when near to expiry or when the certificate has already expired.
<span id="CLOUDFLARE_API_TOKEN">CLOUDFLARE_API_TOKEN</span>           | string | The Cloudflare API token. This value will be used to manage the `TXT` DNS records on the Cloudflare DNS server during the TLS certificate generation. The generated certificate is a wildcard certificate when this parameter is specified.
<span id="OCSERV_KEY">OCSERV_KEY</span>                               | string | The optional secret key for masquerading the `OpenConnect` VPN server identity.
<span id="ENABLE_API">ENABLE_API</span>                               | switch | Enables the [user management API](bypasshub/README.md#-api).
<span id="ENABLE_API_UI">ENABLE_API_UI</span>                         | switch | Enables the web-based UI for interacting with the API.
<span id="API_KEY">API_KEY</span>                                     | string | The secret key for authenticating the API requests.
