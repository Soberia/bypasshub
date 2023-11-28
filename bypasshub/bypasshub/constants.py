from enum import Enum, StrEnum


class PlanUpdateAction(StrEnum):
    UPDATE_PLAN = "update_plan"
    UPDATE_PLAN_EXTRA_TRAFFIC = "update_plan_extra_traffic"
    UPDATE_RESERVED_PLAN = "update_reserved_plan"


class ManagerReason(StrEnum):
    UPDATED_PLAN = "updated plan"
    EXPIRED_PLAN = "expired plan"
    RESERVED_PLAN = "activated reserved plan"
    SYNCHRONIZATION = "database synchronization"
    ZOMBIE_USER = "user doesn't exist on database"


class ServiceState(Enum):
    UNKNOWN = 0
    DELETED = 1
    ADDED = 2


class ServiceStatus(Enum):
    DISCONNECTED = 0
    CONNECTED = 1


class XrayService(StrEnum):
    NAME = "xray"
    ALIAS = "Xray-core"


class OpenConnectService(StrEnum):
    NAME = "ocserv"
    ALIAS = "OpenConnect"
