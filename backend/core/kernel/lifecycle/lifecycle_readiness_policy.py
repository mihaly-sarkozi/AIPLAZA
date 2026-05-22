# backend/core/kernel/lifecycle/lifecycle_readiness_policy.py
# Feladat: A lifecycle readiness döntési szabályait tartalmazza. Startup állapotból és background worker probe eredményből határozza meg, mikor tekinthető az alkalmazás ready-nek, külön kezelve a web-only process disabled worker állapotát. Kernel lifecycle policy a health/readiness service számára.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.lifecycle.lifecycle_state import LifecycleState


class LifecycleReadinessPolicy:
    """Meghatározza, mikor számít ready-nek az alkalmazás.

    instance_role_aware=True (alapértelmezés): ha az aktuális process web-only szerepkörben
    fut (INSTANCE_ROLE=web), a background_worker ellenőrzés automatikusan "disabled"
    eredményt ad - a háttérfeldolgozás egy külön worker-processben fut.
    """

    def startup_check(self, state: LifecycleState) -> tuple[str, bool]:
        startup_complete = bool(state.startup_completed_at) and not state.startup_in_progress
        return ("ok" if startup_complete else "not_ready", startup_complete)

    def background_worker_ready(self, worker_status: str) -> bool:
        """True, ha a background worker állapota elfogadható.

        Elfogadott állapotok:
          running  - a worker szál fut (combined mód)
          disabled - nincs worker ebben a processben (web mód vagy szándékosan kikapcsolt)
        """
        return worker_status in {"running", "disabled"}
