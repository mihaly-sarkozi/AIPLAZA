#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

SKIP_DIR_NAMES = {
    ".git",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".stanza_models",
}


@dataclass(frozen=True)
class ImportRef:
    module: str
    line: int


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    imported_module: str
    rule: str


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for path in BACKEND_ROOT.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        files.append(path)
    return files


def _module_name_from_path(path: Path) -> str:
    rel = path.relative_to(BACKEND_ROOT).as_posix()
    return rel.removesuffix(".py").replace("/", ".")


def _resolve_from_import(current_module: str, node: ast.ImportFrom) -> str:
    module = str(node.module or "").strip()
    if node.level <= 0:
        return module
    parts = current_module.split(".")
    if node.level > len(parts):
        base = []
    else:
        base = parts[: len(parts) - node.level]
    if module:
        base.extend(module.split("."))
    return ".".join(item for item in base if item)


def _collect_imports(path: Path) -> tuple[list[ImportRef], list[str]]:
    parse_errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return [], [f"{path.relative_to(ROOT).as_posix()}:0: read_error: {exc}"]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(text)
    except SyntaxError as exc:
        line = int(getattr(exc, "lineno", 0) or 0)
        return [], [f"{path.relative_to(ROOT).as_posix()}:{line}: parse_error: {exc.msg}"]
    current_module = _module_name_from_path(path)
    imports: list[ImportRef] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = str(alias.name or "").strip()
                if module:
                    imports.append(ImportRef(module=module, line=int(node.lineno or 0)))
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve_from_import(current_module, node)
            if resolved:
                imports.append(ImportRef(module=resolved, line=int(node.lineno or 0)))
    return imports, parse_errors


def _is_router_file(rel: str) -> bool:
    return "/router/" in rel or rel.endswith("/api/router.py")


def _is_repository_file(rel: str) -> bool:
    return "/repositories/" in rel


def _is_concrete_repository_module(module: str) -> bool:
    text = str(module or "").strip()
    if not text:
        return False
    if ".ports.repositories" in text:
        return False
    return ".repositories." in text or text.endswith(".repositories")


_ROUTER_INFRA_ALLOWLIST: dict[str, set[str]] = {
    "backend/apps/chat/router/chat_router.py": {
        "core.infrastructure.audit.const.audit_log_action_const",
        "core.infrastructure.audit.service.audit_service",
    },
    "backend/admin/router/admin_router.py": {
        "core.infrastructure.audit.const.audit_log_action_const",
        "core.infrastructure.audit.service.audit_service",
    },
    "backend/core/modules/tenant/router/tenant_router.py": {
        "core.infrastructure.cache.redis_client",
    },
}


def _collect_violations() -> tuple[list[Violation], list[str]]:
    violations: list[Violation] = []
    parse_errors: list[str] = []
    for path in _iter_python_files():
        rel = path.relative_to(ROOT).as_posix()
        imports, errors = _collect_imports(path)
        parse_errors.extend(errors)
        for item in imports:
            module = item.module
            # Rule 1: chat app nem importálhatja közvetlenül a knowledge repository réteget.
            if rel.startswith("backend/apps/chat/") and module.startswith("apps.knowledge.repositories"):
                violations.append(
                    Violation(
                        path=rel,
                        line=item.line,
                        imported_module=module,
                        rule="chat_cannot_import_knowledge_repositories",
                    )
                )

            # Rule 2: router/api ne importáljon repository vagy deep infra modulokat.
            if _is_router_file(rel):
                if module.startswith("apps.") and _is_concrete_repository_module(module):
                    violations.append(
                        Violation(
                            path=rel,
                            line=item.line,
                            imported_module=module,
                            rule="router_must_not_import_repositories",
                        )
                    )
                if module.startswith("core.infrastructure."):
                    allowed = _ROUTER_INFRA_ALLOWLIST.get(rel, set())
                    if module not in allowed:
                        violations.append(
                            Violation(
                                path=rel,
                                line=item.line,
                                imported_module=module,
                                rule="router_must_not_import_core_infrastructure",
                            )
                        )

            # Rule 3: repository réteg ne importáljon FastAPI-t.
            if _is_repository_file(rel) and module.startswith("fastapi"):
                violations.append(
                    Violation(
                        path=rel,
                        line=item.line,
                        imported_module=module,
                        rule="repository_must_not_import_fastapi",
                    )
                )

            # Rule 4: repository réteg ne függjön router/service rétegtől.
            if _is_repository_file(rel):
                if module.startswith("apps.") and (".router" in module or ".service" in module):
                    violations.append(
                        Violation(
                            path=rel,
                            line=item.line,
                            imported_module=module,
                            rule="repository_must_not_depend_on_router_or_service",
                        )
                    )
    return violations, parse_errors


def main() -> int:
    violations, parse_errors = _collect_violations()
    if parse_errors:
        print("ERROR: import boundary parser/read errors:")
        for item in parse_errors:
            print(f" - {item}")
        return 2
    if not violations:
        print("OK: import boundary checks passed.")
        return 0
    print("ERROR: import boundary violations found:")
    for item in violations:
        print(f" - {item.path}:{item.line}: {item.rule}: {item.imported_module}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
