from __future__ import annotations

import pytest

from tests.architecture._helpers import (
    BACKEND_ROOT,
    collect_imports,
    describe_violation,
    format_violations,
    iter_python_files,
    module_has_segment,
    module_matches_any_prefix,
)

pytestmark = [pytest.mark.architecture, pytest.mark.must_pass]

INTERFACE_ROOT = BACKEND_ROOT / "core" / "kernel" / "interface"
FORBIDDEN_PREFIXES = (
    "fastapi",
    "sqlalchemy",
    "core.kernel.runtime",
    "core.kernel.bootstrap",
)


def _is_forbidden_interface_import(module: str) -> str | None:
    if module_matches_any_prefix(module, FORBIDDEN_PREFIXES):
        return "runtime / framework import"
    if module_has_segment(module, "repositories"):
        return "repository réteg import"
    if module_has_segment(module, "models"):
        return "model réteg import"
    if any(part == "orm" or part.endswith("_orm") for part in module.split(".")):
        return "ORM import"
    return None


def test_interface_package_uses_only_pure_imports() -> None:
    violations: list[str] = []

    for path in iter_python_files(INTERFACE_ROOT):
        for occurrence in collect_imports(path):
            reason = _is_forbidden_interface_import(occurrence.imported_module)
            if reason is None:
                continue
            violations.append(describe_violation(occurrence, detail=reason))

    assert not violations, format_violations(
        rule="Architektúra-szabály sérült: a `core/kernel/interface` csak tiszta interface típusokat és hookokat tartalmazhat.",
        guidance="Az interface réteg ne importáljon runtime-ot, repository-t, modelt, ORM-et vagy frameworköt; csak típusokat, interfészeket, route interface-eket és service key-ket használj.",
        violations=violations,
    )
