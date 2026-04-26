from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.di import module_service_dependency
from apps.contracts.service_keys import (
    MODULE_CHAT_LLM_CLIENT_FACTORY,
    MODULE_CHAT_SERVICE,
    MODULE_KNOWLEDGE_REPOSITORY,
)
from core.platform.composition import ModuleContext
from core.platform.service_keys import PLATFORM_SETTINGS_REPOSITORY, PLATFORM_TENANT_SIGNUP_FACTORY, PLATFORM_USERS_SERVICE


def test_module_context_publishes_only_platform_namespaces():
    context = ModuleContext(
        infrastructure=object(),
        security=object(),
        audit_service=object(),
    )

    with (
        patch("core.di.register_service") as register_service,
        patch("core.di.register_repository") as register_repository,
        patch("core.di.register_factory") as register_factory,
    ):
        context.register_service(PLATFORM_USERS_SERVICE, object())
        context.register_service(MODULE_CHAT_SERVICE, object())

        context.register_repository(PLATFORM_SETTINGS_REPOSITORY, object())
        context.register_repository(MODULE_KNOWLEDGE_REPOSITORY, object())

        context.register_factory(PLATFORM_TENANT_SIGNUP_FACTORY, lambda: None)
        context.register_factory(MODULE_CHAT_LLM_CLIENT_FACTORY, lambda: None)

    assert register_service.call_count == 1
    assert register_service.call_args[0][0] == PLATFORM_USERS_SERVICE

    assert register_repository.call_count == 1
    assert register_repository.call_args[0][0] == PLATFORM_SETTINGS_REPOSITORY

    assert register_factory.call_count == 1
    assert register_factory.call_args[0][0] == PLATFORM_TENANT_SIGNUP_FACTORY


def test_module_service_dependency_rejects_non_module_namespace():
    with pytest.raises(ValueError, match="module\\.\\* namespace"):
        module_service_dependency("platform.users.service")
