import os
import tomllib
from grp import getgrnam
from pathlib import Path

from .types import Config
from .constants import XrayService, OpenConnectService

config: Config = tomllib.loads(
    (
        (
            Path(__file__).parent.with_name("config.toml")
            if (config := os.environ.get("CONFIG_PATH")) is None
            else Path(config)
        )
    ).read_text()
)

profiles = os.environ.get("COMPOSE_PROFILES")
for service in (XrayService, OpenConnectService):
    if service.NAME not in profiles:
        config["main"][f"manage_{service.NAME}"] = False

config["environment"] = {
    variable.lower(): os.environ.get(variable)
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

config["api"]["enable"] = bool(os.environ.get("ENABLE_API"))
config["api"]["ui"] = bool(os.environ.get("ENABLE_API_UI"))
if api_key := Path("/run/secrets/api_key").read_text():
    config["api"]["key"] = api_key
config["api"]["key"] = config["api"]["key"].encode()

if not (temp_path := Path(config["main"]["temp_path"])).exists():
    temp_path.mkdir(mode=0o750, parents=True, exist_ok=True)
    os.chown(temp_path, uid=-1, gid=getgrnam("users").gr_gid)
