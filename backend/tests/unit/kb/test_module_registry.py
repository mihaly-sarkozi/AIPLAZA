from __future__ import annotations

from apps.kb.bootstrap.app_module import KB_MODULES


EXPECTED_MODULE_NAMES = [
    "kb.crud",
    "kb.ingest",
    "kb.understanding",
    "kb.discovery",
    "kb.indexing",
    "kb.search",
    "kb.services",
    "kb.feedback",
    "kb.testing",
    "kb.maintenance",
]


def test_kb_modules_share_registration_contract() -> None:
    assert [module.name for module in KB_MODULES] == EXPECTED_MODULE_NAMES
    for module in KB_MODULES:
        assert callable(module.register_routes)
        assert callable(module.register_services)
        assert callable(module.register_event_handlers)
