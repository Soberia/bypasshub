from typing import ParamSpec, TypeVar, TypedDict, NotRequired, Any
from typing_extensions import TypedDict  # TODO: Should be removed in Python 3.12

from .constants import PlanUpdateAction

Param = ParamSpec("Param")
Return = TypeVar("Return")


class _ConfigMain(TypedDict):
    manage_xray: bool
    manage_openconnect: bool
    max_users: int
    max_active_users: int
    service_timeout: int
    monitor_interval: int
    monitor_passive_steps: int
    monitor_zombies: bool
    temp_path: str
    xray_cdn_ips_path: str
    xray_api_socket_path: str
    occtl_broker_socket_path: str
    nginx_fallback_socket_path: str


class _ConfigLog(TypedDict):
    size: int
    level: str
    store: bool
    stdout_traceback: bool
    path: str


class _ConfigDatabase(TypedDict):
    backup_interval: int
    path: str


class _ConfigApi(TypedDict):
    enable: bool
    ui: bool
    graceful_timeout: int
    key: bytes
    ui_icon: str
    socket_path: str


class _ConfigEnvironment(TypedDict):
    domain: str
    enable_xray_cdn: bool
    enable_xray_subscription: bool
    xray_sni: str
    xray_cdn_sni: str
    tls_port: str
    cdn_tls_port: str


class Config(TypedDict):
    main: _ConfigMain
    log: _ConfigLog
    database: _ConfigDatabase
    api: _ConfigApi
    environment: _ConfigEnvironment


class PlanBase(TypedDict):
    plan_start_date: str | None
    plan_duration: int | None
    plan_traffic: int | None
    plan_extra_traffic: int


class Plan(PlanBase):
    plan_traffic_usage: int
    plan_extra_traffic_usage: int


class Credentials(TypedDict):
    username: str
    uuid: str


class User(Credentials, Plan):
    user_creation_date: str | None
    total_upload: int
    total_download: int


class History(PlanBase):
    id: int | None
    date: str
    action: PlanUpdateAction
    username: str
    plan_extra_traffic: int | None


class DatabaseSchema(TypedDict):
    users: list[User]
    history: list[History]


class Traffic(TypedDict):
    uplink: int
    downlink: int


class SerializedError(TypedDict):
    type: str
    message: str
    group: NotRequired[str]
    code: NotRequired[int]
    cause: NotRequired[list["SerializedError"]]
    payload: NotRequired[Any]


class HTTPSerializedError(TypedDict):
    details: list[SerializedError]


class DataUnits(TypedDict):
    B: str
    kB: str
    MB: str
    GB: str
    TB: str
    PB: str


class TimeUnits(TypedDict):
    s: str
    m: str
    h: str
    d: str
