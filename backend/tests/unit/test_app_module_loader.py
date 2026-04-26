from __future__ import annotations

import sys
import types

import pytest

from apps import _load_module

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_app_module_loader_returns_stable_instance_per_factory_path() -> None:
    module_name = "tests.fake_app_loader_module"
    fake_module = types.ModuleType(module_name)
    calls: list[int] = []

    def make_module() -> object:
        calls.append(1)
        return object()

    fake_module.make_module = make_module
    sys.modules[module_name] = fake_module
    _load_module.cache_clear()
    try:
        first = _load_module(f"{module_name}:make_module")
        second = _load_module(f"{module_name}:make_module")
    finally:
        sys.modules.pop(module_name, None)
        _load_module.cache_clear()

    assert first is second
    assert calls == [1]
