from __future__ import annotations

from apps.kb.bootstrap.app_module import KB_MODULES


def test_kb_modules_share_registration_contract() -> None:
    assert len(KB_MODULES) == 8
    for module in KB_MODULES:
        assert module.name.startswith("kb.")
        assert callable(module.register_routes)
        assert callable(module.register_services)
        assert callable(module.register_event_handlers)
