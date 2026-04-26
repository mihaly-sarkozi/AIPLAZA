from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LifecycleProbePort(Protocol):
    def check_database(self) -> str: ...

    def check_cache(self) -> str: ...

    def check_background_worker(self) -> str: ...


__all__ = ["LifecycleProbePort"]
