from __future__ import annotations

from typing import Any


class HeadingPathTracker:
    def __init__(self) -> None:
        self._stack: list[tuple[int, str]] = []

    def update(self, heading_level: int, text: str) -> dict[str, Any]:
        level = max(0, int(heading_level))
        while self._stack and self._stack[-1][0] >= level:
            self._stack.pop()
        self._stack.append((level, text[:512]))
        return self.snapshot(current_section_title=text[:512])

    def current(self) -> dict[str, Any]:
        return self.snapshot()

    def snapshot(self, *, current_section_title: str | None = None) -> dict[str, Any]:
        path = [title for _, title in self._stack]
        levels = [level for level, _ in self._stack]
        section = current_section_title or (path[-1] if path else None)
        return {
            "heading_path": path,
            "heading_levels": levels,
            "current_section_title": section,
        }


__all__ = ["HeadingPathTracker"]
