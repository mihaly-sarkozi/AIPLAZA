from __future__ import annotations

from typing import Any, Callable

from apps.kb.kb_discovery.enums.DiscoveryStep import DiscoveryStep


class BaseDiscoveryStep:
    """Pipeline lépés wrapper — a DiscoveryPipelineService hívja."""

    step: DiscoveryStep

    def __init__(self, step: DiscoveryStep) -> None:
        self.step = step

    def run(self, action: Callable[[], Any]) -> Any:
        return action()


__all__ = ["BaseDiscoveryStep"]
