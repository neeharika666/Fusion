from __future__ import annotations

from dataclasses import dataclass

from accounts.models import ExtraInfo


class ActingRole:
    EMPLOYEE = "EMPLOYEE"
    DEPADMIN = "DEPADMIN"
    PS_ADMIN = "PS_ADMIN"
    HOD = "HOD"
    REGISTRAR = "REGISTRAR"
    DIRECTOR = "DIRECTOR"


def get_acting_role(request) -> str:
    role = (request.headers.get("X-Acting-Role") or "").strip().upper()
    return role


def require_extrainfo(user) -> ExtraInfo:
    # Lazy import to avoid circular dependency:
    # selectors imports ActingRole from this module.
    from ps.selectors import get_extrainfo_for_user

    return get_extrainfo_for_user(user)


def user_is_hod(extrainfo: ExtraInfo) -> bool:
    from ps.selectors import is_user_hod

    return is_user_hod(extrainfo)


def user_has_designation(extrainfo: ExtraInfo, name_contains: str) -> bool:
    from ps.selectors import has_designation

    return has_designation(extrainfo, name_contains)


@dataclass(frozen=True)
class ActorContext:
    role: str
    extrainfo: ExtraInfo


def get_actor_context(request) -> ActorContext:
    extrainfo = require_extrainfo(request.user)
    role = get_acting_role(request)
    if role == ActingRole.EMPLOYEE:
        return ActorContext(role=role, extrainfo=extrainfo)
    if role == ActingRole.DEPADMIN and user_has_designation(extrainfo, "depadmin"):
        return ActorContext(role=role, extrainfo=extrainfo)
    if role == ActingRole.PS_ADMIN and user_has_designation(extrainfo, "ps admin"):
        return ActorContext(role=role, extrainfo=extrainfo)
    if role == ActingRole.HOD and user_is_hod(extrainfo):
        return ActorContext(role=role, extrainfo=extrainfo)
    if role == ActingRole.REGISTRAR and user_has_designation(extrainfo, "registrar"):
        return ActorContext(role=role, extrainfo=extrainfo)
    if role == ActingRole.DIRECTOR and user_has_designation(extrainfo, "director"):
        return ActorContext(role=role, extrainfo=extrainfo)
    raise PermissionError("Invalid or unauthorized acting role")
