from __future__ import annotations

import pytest

from tests.architecture._helpers import CORE_ROOT, collect_imports, describe_violation, format_violations, iter_python_files

pytestmark = [pytest.mark.architecture, pytest.mark.must_pass]


def test_core_does_not_import_apps() -> None:
    violations: list[str] = []

    for path in iter_python_files(CORE_ROOT):
        for occurrence in collect_imports(path):
            if occurrence.imported_module == "apps" or occurrence.imported_module.startswith("apps."):
                violations.append(
                    describe_violation(
                        occurrence,
                        detail="a `core` nem függhet az alkalmazásrétegtől",
                    )
                )

    assert not violations, format_violations(
        rule="Architektúra-szabály sérült: a `core/` nem importálhat `apps` namespace-et.",
        guidance="Az irány mindig `apps -> core`; app-specifikus integrációhoz platform interface-t, hookot vagy registry-t használj.",
        violations=violations,
    )
