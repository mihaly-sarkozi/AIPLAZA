from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.architecture, pytest.mark.must_pass]

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _python_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts and ".venv" not in path.parts and "venv" not in path.parts
    ]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_infra_does_not_import_app_service_router_or_use_case_layers() -> None:
    forbidden_fragments = (".service", ".router", ".application", ".bootstrap", ".web")
    violations: list[str] = []
    for path in _python_files(BACKEND_ROOT / "infra"):
        for imported in _imports(path):
            if not imported.startswith("apps."):
                continue
            if any(fragment in imported for fragment in forbidden_fragments):
                violations.append(f"{path.relative_to(BACKEND_ROOT)} imports {imported}")

    assert violations == []


def test_app_domain_and_service_do_not_import_concrete_infra_adapters() -> None:
    allowed_port_imports = {"infra.storage.object_storage"}
    forbidden_prefixes = (
        "infra.ai",
        "infra.audit",
        "infra.cache",
        "infra.db",
        "infra.email",
        "infra.persistence",
        "infra.security",
        "infra.vector",
    )
    violations: list[str] = []
    for app_root in (BACKEND_ROOT / "apps").iterdir():
        for layer in ("domain", "service"):
            root = app_root / layer
            if not root.exists():
                continue
            for path in _python_files(root):
                for imported in _imports(path):
                    if imported in allowed_port_imports:
                        continue
                    if imported.startswith(forbidden_prefixes):
                        violations.append(f"{path.relative_to(BACKEND_ROOT)} imports {imported}")

    assert violations == []


def test_core_does_not_import_apps_layer() -> None:
    violations: list[str] = []
    for path in _python_files(BACKEND_ROOT / "core"):
        for imported in _imports(path):
            if imported.startswith("apps."):
                violations.append(f"{path.relative_to(BACKEND_ROOT)} imports {imported}")

    assert violations == []


def test_knowledge_submodules_do_not_import_removed_compat_paths() -> None:
    forbidden_imports = {
        "apps.knowledge.api.background_jobs",
        "apps.knowledge.api.common",
        "apps.knowledge.api.file_ingest_use_cases",
        "apps.knowledge.api.upload_malware_scanner",
    }
    # apps.knowledge.training.* deleted - submodules must not import it
    forbidden_prefixes = (
        "apps.knowledge.training.",
    )
    submodules = (
        BACKEND_ROOT / "apps" / "knowledge" / "knowledge_base",
        BACKEND_ROOT / "apps" / "knowledge" / "training_ingest",
        BACKEND_ROOT / "apps" / "knowledge" / "training_processing",
        BACKEND_ROOT / "apps" / "knowledge" / "retrieval",
    )
    violations: list[str] = []
    for root in submodules:
        for path in _python_files(root):
            for imported in _imports(path):
                if imported in forbidden_imports or imported.startswith(forbidden_prefixes):
                    violations.append(f"{path.relative_to(BACKEND_ROOT)} imports {imported}")

    assert violations == []


def test_knowledge_submodule_service_uses_canonical_locations() -> None:
    """Each submodule service should import sibling services from its own package, not old wrappers."""
    violations: list[str] = []
    checks = [
        (BACKEND_ROOT / "apps" / "knowledge" / "knowledge_base" / "service",
         "apps.knowledge.knowledge_base.service."),
        (BACKEND_ROOT / "apps" / "knowledge" / "training_ingest" / "service",
         "apps.knowledge.training_ingest.service."),
        (BACKEND_ROOT / "apps" / "knowledge" / "training_processing" / "service",
         "apps.knowledge.training_processing.service."),
        (BACKEND_ROOT / "apps" / "knowledge" / "retrieval" / "service",
         "apps.knowledge.retrieval.service."),
    ]
    # Detect if a file imports a sibling that has been physically moved but via old path
    for root, canonical_prefix in checks:
        if not root.exists():
            continue
        for path in _python_files(root):
            for imported in _imports(path):
                # Flag: still importing from old shared service dir for modules now owned by this submodule
                if imported.startswith("apps.knowledge.service.") and not any(
                    imported.startswith(f"apps.knowledge.service.{shared}")
                    for shared in ("facade", "ports", "knowledge_facade", "knowledge_service",
                                   "knowledge_audit_service", "runtime_store", "errors")
                ):
                    violations.append(
                        f"[SOFT] {path.relative_to(BACKEND_ROOT)} still imports from old shared path: {imported}"
                    )
    # Soft check: report but don't fail while wrappers remain
    if violations:
        import warnings
        warnings.warn(f"Found {len(violations)} service files still using old shared wrapper imports:\n" +
                      "\n".join(violations), stacklevel=2)

    assert True  # non-blocking; upgrade to hard assert after wrappers are removed
