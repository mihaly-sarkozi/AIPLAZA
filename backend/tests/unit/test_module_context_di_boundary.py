from __future__ import annotations

import pytest

from apps.chat.bootstrap.service_keys import CHAT_LLM_CLIENT_FACTORY, CHAT_SERVICE
from apps.kb.kb_ingest.bootstrap.service_keys import KB_INGEST_REPOSITORY
from core.kernel.http.app_dependencies import module_service_dependency
from core.kernel.interface.module_context import ModuleContext
from core.kernel.interface.keys import PLATFORM_SETTINGS_REPOSITORY, PLATFORM_TENANT_SIGNUP_FACTORY, PLATFORM_USERS_SERVICE


def test_module_context_publishes_only_platform_namespaces():
    published_services: list[str] = []
    published_repositories: list[str] = []
    published_factories: list[str] = []
    context = ModuleContext(
        infrastructure=object(),
        security=object(),
        audit_service=object(),
        service_publisher=lambda name, _instance: published_services.append(name),
        repository_publisher=lambda name, _instance: published_repositories.append(name),
        factory_publisher=lambda name, _factory: published_factories.append(name),
    )

    context.register_service(PLATFORM_USERS_SERVICE, object())
    context.register_service(CHAT_SERVICE, object())

    context.register_repository(PLATFORM_SETTINGS_REPOSITORY, object())
    context.register_repository(KB_INGEST_REPOSITORY, object())

    context.register_factory(PLATFORM_TENANT_SIGNUP_FACTORY, lambda: None)
    context.register_factory(CHAT_LLM_CLIENT_FACTORY, lambda: None)

    assert published_services == [PLATFORM_USERS_SERVICE]

    assert published_repositories == [PLATFORM_SETTINGS_REPOSITORY]

    assert published_factories == [PLATFORM_TENANT_SIGNUP_FACTORY]


def test_module_service_dependency_rejects_non_module_namespace():
    with pytest.raises(ValueError, match="module\\.\\* namespace"):
        module_service_dependency("platform.users.service")
