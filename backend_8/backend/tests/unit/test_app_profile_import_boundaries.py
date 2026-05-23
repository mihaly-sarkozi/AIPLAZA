from __future__ import annotations

import importlib
import sys

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_importing_profile_service_module_does_not_load_app_wiring() -> None:
    for module_name in (
        "apps.profile.module",
        "apps.profile.service.profile_facade",
        "apps.profile.service",
        "apps.profile",
    ):
        sys.modules.pop(module_name, None)

    importlib.import_module("apps.profile.service.profile_facade")

    assert "apps.profile.module" not in sys.modules
