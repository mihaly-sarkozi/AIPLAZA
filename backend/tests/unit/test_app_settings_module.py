from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.settings.bootstrap.service_keys import SETTINGS_SERVICE
from apps.settings.bootstrap.app_module import SettingsAppModule
from core.kernel.interface import ModuleContext
from core.kernel.interface.keys import PLATFORM_SETTINGS_SERVICE

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _CoreSettingsService:
    def get_settings_snapshot(self) -> dict[str, object]:
        return {
            "two_factor_enabled": False,
            "timezone": "UTC",
            "date_format": "YYYY-MM-DD",
            "time_format": "HH:mm",
        }

    def update_settings(self, **kwargs) -> dict[str, object]:
        return self.get_settings_snapshot()


def _context() -> ModuleContext:
    return ModuleContext(
        infrastructure=SimpleNamespace(db_session_factory=SimpleNamespace()),
        security=SimpleNamespace(),
        audit_service=SimpleNamespace(),
    )


def test_settings_module_registers_facade_service() -> None:
    module = SettingsAppModule()
    context = _context()
    context.register_service(PLATFORM_SETTINGS_SERVICE, _CoreSettingsService())

    module.register(context)

    facade = context.get_service(SETTINGS_SERVICE)
    assert facade.get_settings()["timezone"] == "UTC"


def test_settings_module_declares_expected_contract() -> None:
    module = SettingsAppModule()

    assert module.service_dependencies() == (PLATFORM_SETTINGS_SERVICE,)
    assert module.permissions() == ("settings.read", "settings.write")

    routes = module.routers()
    assert len(routes) == 1
    assert routes[0].prefix == "/api"
    assert routes[0].tags == ("settings",)
