from __future__ import annotations

import ast
from pathlib import Path

from core.capabilities.audit.const.audit_log_action_const import AuditLogAction


_SERVICE_FILES = [
    Path("core/capabilities/auth/service/login_service.py"),
    Path("core/capabilities/auth/service/refresh_service.py"),
    Path("core/capabilities/auth/service/logout_service.py"),
    Path("core/capabilities/users/service/user_service.py"),
    Path("core/capabilities/users/service/invite_service.py"),
    Path("core/platform/settings/services.py"),
    Path("core/platform/brand/services.py"),
    Path("core/platform_admin/router.py"),
    Path("core/extensions/tenant/signup/new_demo_signup.py"),
]


def _collect_audit_action_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        action_expr = None

        # Közvetlen audit.log(AuditLogAction.X, ...)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "log":
            action_expr = node.args[0] if node.args else None
            if isinstance(action_expr, ast.Name):
                # Wrapper függvény belső továbbadása (pl. audit.log(action, ...)) itt nem ellenőrizhető.
                continue

        # Wrapper hívás: _audit_log(audit, AuditLogAction.X, ...)
        elif isinstance(node.func, ast.Name) and node.func.id == "_audit_log":
            action_expr = node.args[1] if len(node.args) > 1 else None
        else:
            continue

        assert action_expr is not None, f"Audit action missing in {path}"
        assert isinstance(action_expr, ast.Attribute), f"Audit action must be enum member in {path}"
        assert isinstance(action_expr.value, ast.Name), f"Audit action owner must be named in {path}"
        assert action_expr.value.id == "AuditLogAction", f"Audit action must use AuditLogAction in {path}"
        names.add(action_expr.attr)

    return names


def test_audit_log_calls_use_only_audit_action_enum_members():
    used_names: set[str] = set()
    for rel_path in _SERVICE_FILES:
        used_names.update(_collect_audit_action_names(rel_path))

    enum_names = {member.name for member in AuditLogAction}
    assert used_names <= enum_names


def test_all_audit_action_enum_members_are_accounted_for_in_service_usage():
    used_names: set[str] = set()
    for rel_path in _SERVICE_FILES:
        used_names.update(_collect_audit_action_names(rel_path))

    enum_names = {member.name for member in AuditLogAction}
    unused = enum_names - used_names

    # Legacy compatibility constants: defined, de jelenleg nincs aktív service kibocsátójuk.
    assert unused == {"LOGOUT_ERROR", "KNOWLEDGE_PII_DEPERSONALIZED"}
