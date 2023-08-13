import tomllib
from os import environ
from pathlib import Path

from .types import Config, XrayService, OpenConnectService

config: Config = tomllib.loads(
    (
        (
            Path(__file__).parent.with_name("config.toml")
            if (config := environ.get("CONFIG_PATH")) is None
            else Path(config)
        )
    ).read_text()
)

profiles = environ.get("COMPOSE_PROFILES")
for service in (XrayService, OpenConnectService):
    if service.NAME not in profiles:
        config["main"][f"monitor_{service.NAME}"] = False

config["environment"] = {
    variable.lower(): environ.get(variable)
    for variable in (
        "DOMAIN",
        "ENABLE_XRAY_CDN",
        "ENABLE_XRAY_SUBSCRIPTION",
        "XRAY_SNI",
        "XRAY_CDN_SNI",
        "TLS_PORT",
        "CDN_TLS_PORT",
    )
}

for key in ("enable_xray_cdn", "enable_xray_subscription"):
    config["environment"][key] = bool(config["environment"][key])

config["api"]["enable"] = bool(environ.get("ENABLE_API"))
config["api"]["ui"] = bool(environ.get("ENABLE_API_UI"))

if api_key := environ.get("API_KEY"):
    config["api"]["key"] = api_key
config["api"]["key"] = config["api"]["key"].encode()

if not (temp_path := Path(config["main"]["temp_path"])).exists():
    temp_path.mkdir(parents=True, exist_ok=True)
