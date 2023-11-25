from enum import StrEnum


class PlanUpdateAction(StrEnum):
    UPDATE_PLAN = "update_plan"
    UPDATE_PLAN_EXTRA_TRAFFIC = "update_plan_extra_traffic"


class XrayService(StrEnum):
    NAME = "xray"
    ALIAS = "Xray-core"


class OpenConnectService(StrEnum):
    NAME = "ocserv"
    ALIAS = "OpenConnect"
