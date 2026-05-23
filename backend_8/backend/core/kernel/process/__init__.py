# backend/core/kernel/process/__init__.py
# Feladat: Stabil public process/runtime dontesi exportfelulet app modulok
# szamara. Elrejti a core.kernel.runtime belso assembly moduljait az apps
# reteg elol.

from __future__ import annotations

from core.kernel.runtime.instance_role import should_run_background_workers

__all__ = ["should_run_background_workers"]
