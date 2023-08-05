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

# 🔨 Development

The development environment is leveraged by [VSCode's Dev Containers](https://code.visualstudio.com/docs/devcontainers/containers).
