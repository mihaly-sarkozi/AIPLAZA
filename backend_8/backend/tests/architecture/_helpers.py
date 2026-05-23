from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

BACKEND_ROOT = Path(__file__).resolve().parents[2]
CORE_ROOT = BACKEND_ROOT / "core"
APPS_ROOT = BACKEND_ROOT / "apps"
KERNEL_ROOT = BACKEND_ROOT / "core" / "kernel"


@dataclass(frozen=True)
class ImportOccurrence:
    source_path: Path
    imported_module: str
    lineno: int
    statement: str

    @property
    def relative_source(self) -> Path:
        return self.source_path.relative_to(BACKEND_ROOT)


def iter_python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def iter_direct_child_directories(root: Path) -> list[Path]:
    return sorted(path for path in root.iterdir() if path.is_dir())


def parse_python_file(path: Path) -> tuple[str, ast.AST]:
    source = path.read_text(encoding="utf-8")
    return source, ast.parse(source, filename=str(path))


def collect_imports(path: Path) -> list[ImportOccurrence]:
    source, tree = parse_python_file(path)
    imports: list[ImportOccurrence] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            statement = ast.get_source_segment(source, node) or "import ..."
            for alias in node.names:
                imports.append(
                    ImportOccurrence(
                        source_path=path,
                        imported_module=alias.name,
                        lineno=node.lineno,
                        statement=statement,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            if not node.module:
                continue
            statement = ast.get_source_segment(source, node) or "from ... import ..."
            imports.append(
                ImportOccurrence(
                    source_path=path,
                    imported_module=node.module,
                    lineno=node.lineno,
                    statement=statement,
                )
            )

    return imports


def module_matches_prefix(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def module_matches_any_prefix(module: str, prefixes: Iterable[str]) -> bool:
    return any(module_matches_prefix(module, prefix) for prefix in prefixes)


def module_has_segment(module: str, segment: str) -> bool:
    return segment in module.split(".")


def app_name_from_path(path: Path) -> str | None:
    try:
        return path.relative_to(APPS_ROOT).parts[0]
    except (ValueError, IndexError):
        return None


def app_name_from_module(module: str) -> str | None:
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != "apps":
        return None
    return parts[1]


def format_violations(*, rule: str, guidance: str, violations: Iterable[str]) -> str:
    rendered = "\n".join(f"- {line}" for line in violations)
    return f"{rule}\nHelyes irány: {guidance}\n{rendered}"


def describe_violation(occurrence: ImportOccurrence, *, detail: str) -> str:
    return (
        f"{occurrence.relative_source}:{occurrence.lineno} "
        f"tiltott import `{occurrence.imported_module}` ({detail}); "
        f"utasítás: `{occurrence.statement}`"
    )
