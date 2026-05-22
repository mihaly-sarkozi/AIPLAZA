from __future__ import annotations

import pytest

from core.kernel.interface.public_api import (
    APP_PLATFORM_SUPPORT_DIRECTORIES,
    PUBLIC_SHARED_APPS_PREFIXES,
)
from tests.architecture._helpers import (
    APPS_ROOT,
    app_name_from_module,
    app_name_from_path,
    collect_imports,
    describe_violation,
    format_violations,
    iter_python_files,
    module_matches_any_prefix,
)

pytestmark = [pytest.mark.architecture, pytest.mark.must_pass]


def test_apps_do_not_import_other_app_implementations() -> None:
    violations: list[str] = []

    for path in iter_python_files(APPS_ROOT):
        source_app = app_name_from_path(path)
        if not source_app or source_app in APP_PLATFORM_SUPPORT_DIRECTORIES:
            continue

        for occurrence in collect_imports(path):
            if not occurrence.imported_module.startswith("apps."):
                continue
            if module_matches_any_prefix(occurrence.imported_module, PUBLIC_SHARED_APPS_PREFIXES):
                continue

            target_app = app_name_from_module(occurrence.imported_module)
            if target_app in {None, source_app}:
                continue

            violations.append(
                describe_violation(
                    occurrence,
                    detail=(
                        f"másik app implementációjára mutat (`{source_app}` -> `{target_app}`)"
                    ),
                )
            )

    assert not violations, format_violations(
        rule=(
            "Architektúra-szabály sérült: egy app modul nem importálhatja "
            "közvetlenül egy másik app belső implementációját."
        ),
        guidance=(
            "Cross-app együttműködéshez közös interface-t használj az "
            "`core.kernel.interface` alatt, vagy a `core` publikus extension/interface "
            "felületein keresztül kapcsolódj."
        ),
        violations=violations,
    )
