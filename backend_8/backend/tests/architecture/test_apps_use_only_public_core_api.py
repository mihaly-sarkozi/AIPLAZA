from __future__ import annotations

import pytest

from core.kernel.interface.public_api import PUBLIC_CORE_API_PREFIXES
from tests.architecture._helpers import (
    APPS_ROOT,
    collect_imports,
    describe_violation,
    format_violations,
    iter_python_files,
    module_matches_any_prefix,
)

pytestmark = [pytest.mark.architecture, pytest.mark.must_pass]


def test_apps_import_only_declared_public_core_api() -> None:
    violations: list[str] = []

    for path in iter_python_files(APPS_ROOT):
        for occurrence in collect_imports(path):
            if not occurrence.imported_module.startswith("core"):
                continue
            if module_matches_any_prefix(occurrence.imported_module, PUBLIC_CORE_API_PREFIXES):
                continue
            violations.append(
                describe_violation(
                    occurrence,
                    detail="nem publikus `core` namespace",
                )
            )

    assert not violations, format_violations(
        rule="Architektúra-szabály sérült: az `apps/` csak a kijelölt publikus `core` API-t használhatja.",
        guidance="Új app-oldali függéshez vagy a központi `tests/architecture/public_core_api.py` listába kell felvenni a stabil publikus namespace-et, vagy publikus exportfelületet kell létrehozni a `core` oldalon.",
        violations=violations,
    )
