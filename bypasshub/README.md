This container manages the users for all the available services (`Xray-core`, `OpenConnect`) on the fly.

# ⌨️ CLI

To see all the available options, run this command:

```bash
docker compose exec bypasshub bypasshub --help
```

For example, you can run the following command to create a user: (generates a random password, keep it)

```bash
docker compose exec bypasshub bypasshub user --add USERNAME
```

or, for removing a user:

```bash
docker compose exec bypasshub bypasshub user --delete USERNAME
```

The created user has no time or traffic usage restrictions. You can limit the user's traffic usage to 1GB for one month with the following command. If either time or traffic is consumed, the user won't be able to connect to the services anymore.

```bash
docker compose exec bypasshub bypasshub plan \
  --start-date $(date +%s) \
  --duration $(( 30 * 24 * 3600 )) \
  --traffic $(( 10 ** 9 )) \
  USERNAME
```

# 🌩️ API

To use the RESTful API to manage the users, enable the [`ENABLE_API`](../README.md#ENABLE_API) and [`ENABLE_API_UI`](../README.md#ENABLE_API_UI) parameters and set the API secret key with [`API_KEY`](../README.md#API_KEY) parameter. Then, you can access the API endpoints documentations on the browser with `https://$DOMAiN:$TLS_PORT/api?api-key=$API_KEY` URL. It's possible to send the request directly from the browser, however, if you want to use something like `cURL` or send the requests programatically, you can disable the [`ENABLE_API_UI`](../README.md#ENABLE_API_UI) parameter. The secret key also can be provided as a header with `X-API-Key` name or as mentioned with `api-key` query parameter.

> **Note**  
> HTTP 404 error will be returned as response for the authentication failures.

# 🔧 Configuration

Most of the `config.toml` file parameters can be modified while some of them will be replaced by the environment variables provided with the global `.env` file.

# 🔨 Development

The development environment is leveraged by [VSCode's Dev Containers](https://code.visualstudio.com/docs/devcontainers/containers).
