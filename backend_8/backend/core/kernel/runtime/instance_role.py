# backend/core/kernel/runtime/instance_role.py
# Feladat: Az aktuális process szerepét és worker indítási döntéseit kezeli env varok alapján. A web, worker és combined módokból vezeti le, futtathat-e a process HTTP-t, standalone outbox/billing loopot vagy beágyazott háttérszálat. Core runtime orchestration helper deployment szerepkörökhöz.
# Sárközi Mihály - 2026.05.21

"""Instance szerepkör (process role) döntések runtime orchestrationhöz."""
from __future__ import annotations

import os
from enum import Enum


class InstanceRole(str, Enum):
    """Az aktuális process szerepköre a telepítésben."""
    WEB = "web"
    WORKER = "worker"
    COMBINED = "combined"


_VALID_ROLES = {r.value for r in InstanceRole}


def _env_flag(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def get_instance_role() -> InstanceRole:
    """Visszaadja a INSTANCE_ROLE env var alapján az aktuális szerepkört."""
    raw = (os.environ.get("INSTANCE_ROLE") or "combined").strip().lower()
    if raw not in _VALID_ROLES:
        valid = sorted(_VALID_ROLES)
        raise ValueError(
            f"INSTANCE_ROLE érvénytelen érték: {raw!r}. "
            f"Megengedett értékek: {valid}"
        )
    return InstanceRole(raw)


def is_web_process() -> bool:
    """True, ha ez a process HTTP kéréseket szolgál ki (web vagy combined mód)."""
    return get_instance_role() in {InstanceRole.WEB, InstanceRole.COMBINED}


def is_worker_process() -> bool:
    """True, ha ez a process háttérfeladatokat dolgoz fel (worker vagy combined mód)."""
    return get_instance_role() in {InstanceRole.WORKER, InstanceRole.COMBINED}


def should_run_background_workers() -> bool:
    """True, ha ebben a processben beágyazott outbox poll szál indulhat."""
    return get_instance_role() == InstanceRole.COMBINED


def should_run_standalone_outbox_worker() -> bool:
    """True, ha a standalone worker process futtathat outbox loopot."""
    role = get_instance_role()
    if role not in {InstanceRole.WORKER, InstanceRole.COMBINED}:
        return False
    return _env_flag("OUTBOX_WORKER_LOOP_ENABLED", default=True)


def should_run_standalone_billing_worker() -> bool:
    """True, ha a standalone worker process futtathat periodikus billing loopot."""
    role = get_instance_role()
    if role not in {InstanceRole.WORKER, InstanceRole.COMBINED}:
        return False
    return _env_flag("BILLING_WORKER_LOOP_ENABLED", default=True)


__all__ = [
    "InstanceRole",
    "get_instance_role",
    "is_web_process",
    "is_worker_process",
    "should_run_background_workers",
    "should_run_standalone_billing_worker",
    "should_run_standalone_outbox_worker",
]
