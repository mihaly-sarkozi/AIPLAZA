from __future__ import annotations

import importlib
import sys

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_importing_settings_facade_does_not_load_app_module() -> None:
    for module_name in (
        "apps.settings.module",
        "apps.settings.service.settings_facade",
        "apps.settings.service",
        "apps.settings",
    ):
        sys.modules.pop(module_name, None)

    importlib.import_module("apps.settings.service.settings_facade")

    assert "apps.settings.module" not in sys.modules
