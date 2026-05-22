#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCAN_ROOTS = (
    ROOT / "backend",
    ROOT / "scripts",
)

FILE_EXTENSIONS = {".py", ".sql"}

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
}

SKIP_PATH_PARTS = {
    "tests",
    "test_results",
    "site-packages",
}

ALLOWED_PREFIXES = (
    "backend/core/modules/tenant/schema/",
    "backend/migrations/",
    "backend/scripts/",
    "scripts/",
)

DDL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ALTER TABLE", re.compile(r"\bALTER\s+TABLE\b", re.IGNORECASE)),
    ("CREATE INDEX", re.compile(r"\bCREATE\s+INDEX\b", re.IGNORECASE)),
    ("CREATE TABLE", re.compile(r"\bCREATE\s+TABLE\b", re.IGNORECASE)),
    ("DROP TABLE", re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE)),
    ("ensure_column", re.compile(r"\bensure_column\b")),
    ("ensure_*_column", re.compile(r"\bensure_[a-zA-Z0-9_]*_column\b")),
)


def _normalized_rel_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _is_allowed_path(path: Path) -> bool:
    rel = _normalized_rel_path(path)
    if any(part in SKIP_PATH_PARTS for part in path.parts):
        return True
    return any(rel.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def _should_scan(path: Path) -> bool:
    if path.suffix.lower() not in FILE_EXTENSIONS:
        return False
    if any(part in SKIP_DIR_NAMES or part.startswith(".venv") for part in path.parts):
        return False
    return True


def _iter_candidate_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if _should_scan(path):
                files.append(path)
    return files


def _collect_violations() -> list[str]:
    violations: list[str] = []
    for path in _iter_candidate_files():
        if _is_allowed_path(path):
            continue
        rel = _normalized_rel_path(path)
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError as exc:
            violations.append(f"{rel}:0: read_error: {exc}")
            continue
        for line_no, line in enumerate(lines, start=1):
            for label, pattern in DDL_PATTERNS:
                if pattern.search(line):
                    violations.append(f"{rel}:{line_no}: {label}: {line.strip()}")
    return violations


def main() -> int:
    violations = _collect_violations()
    if not violations:
        print("OK: no runtime DDL patterns outside allowed migration/schema paths.")
        return 0

    print("ERROR: runtime DDL patterns found outside allowed paths:")
    for item in violations:
        print(f" - {item}")
    print(
        "\nAllowed paths: "
        "backend/core/modules/tenant/schema/, backend/migrations/, backend/scripts/, scripts/"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
