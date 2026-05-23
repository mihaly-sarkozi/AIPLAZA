from __future__ import annotations

import pytest

from tests.architecture._helpers import BACKEND_ROOT, collect_imports, describe_violation, format_violations, module_has_segment

pytestmark = [pytest.mark.architecture, pytest.mark.must_pass]

PURE_LAYER_FILES = (
    *sorted((BACKEND_ROOT / "core" / "platform").glob("*/services.py")),
    *sorted((BACKEND_ROOT / "core" / "platform").glob("*/policies.py")),
    BACKEND_ROOT / "core" / "modules" / "auth" / "domain" / "authorization_policy.py",
    BACKEND_ROOT / "core" / "kernel" / "security" / "auth_policy_guards.py",
    BACKEND_ROOT / "core" / "modules" / "tenant" / "domain" / "tenant_policy.py",
)


def _is_forbidden_pure_layer_import(module: str) -> str | None:
    parts = module.split(".")
    if module == "sqlalchemy" or module.startswith("sqlalchemy."):
        return "SQLAlchemy import"
    if module_has_segment(module, "repositories"):
        return "concrete repository implementáció import"
    if any(part == "orm" or part.endswith("_orm") for part in parts):
        return "ORM modell import"
    if module_has_segment(module, "models") and any(part.endswith("_orm") for part in parts):
        return "ORM modell import"
    return None


def test_pure_services_and_policies_do_not_import_orm_or_repositories() -> None:
    violations: list[str] = []

    for path in PURE_LAYER_FILES:
        for occurrence in collect_imports(path):
            reason = _is_forbidden_pure_layer_import(occurrence.imported_module)
            if reason is None:
                continue
            violations.append(describe_violation(occurrence, detail=reason))

    assert not violations, format_violations(
        rule="Architektúra-szabály sérült: a pure service/policy réteg nem importálhat ORM-et vagy concrete repository implementációt.",
        guidance="A pure service/policy réteg protocolra, portra vagy tiszta DTO-ra támaszkodjon; a concrete repository wiring a runtime/module rétegben történjen.",
        violations=violations,
    )
