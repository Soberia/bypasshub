from threading import Lock
from datetime import datetime
from typing import TypedDict, Literal, NotRequired, Any, TYPE_CHECKING

from . import constants

if TYPE_CHECKING:
    from .managers import Xray, OpenConnect

type Service = Xray | OpenConnect


class _ConfigMain(TypedDict):
    manage_xray: bool
    manage_ocserv: bool
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


class _PlanConstraint(TypedDict):
    plan_duration: int | None
    plan_traffic: int | None


class _PlanBase(_PlanConstraint):
    plan_start_date: datetime | None
    plan_extra_traffic: int


class Plan(_PlanBase):
    plan_traffic_usage: int
    plan_extra_traffic_usage: int


class Credentials(TypedDict):
    username: str
    uuid: str


class User(Credentials, Plan):
    user_creation_date: datetime | None
    user_latest_activity_date: datetime | None
    total_upload: int
    total_download: int


class ReservedPlan(_PlanConstraint):
    plan_reserved_date: datetime | None


class UserReservedPlan(ReservedPlan):
    username: str


class History(_PlanBase):
    id: int | None
    date: datetime
    action: constants.PlanUpdateAction
    username: str
    plan_extra_traffic: int | None


class DatabaseSchema(TypedDict):
    users: list[User]
    reserved_plans: list[UserReservedPlan]
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


class _ManagerUserState(TypedDict):
    lock: Lock
    synced: bool
    has_active_plan: bool
    services: dict[
        Literal[constants.XrayService.NAME, constants.OpenConnectService.NAME],
        constants.ServiceState,
    ]


class ManagerState(TypedDict):
    reasons: dict[str, constants.ManagerReason]
    users: dict[str, _ManagerUserState]
