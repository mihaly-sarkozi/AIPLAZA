from __future__ import annotations

import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from apps.knowledge.api.router import create_file_source, router as knowledge_api_router
from apps.knowledge.service.knowledge_facade import KnowledgeFacade

pytestmark = pytest.mark.unit


def test_legacy_ingest_routes_are_not_registered() -> None:
    route_paths = {getattr(route, "path", "") for route in knowledge_api_router.routes}
    assert "/kb/{uuid}/ingest-training" not in route_paths
    assert "/kb/{uuid}/ingest-training-file" not in route_paths


def test_legacy_direct_file_source_endpoint_is_deprecated_and_locked() -> None:
    route = next(
        route
        for route in knowledge_api_router.routes
        if getattr(route, "path", "") == "/knowledge/corpora/{corpus_uuid}/sources/file"
    )

    assert getattr(route, "deprecated", False) is True


@pytest.mark.anyio
async def test_legacy_direct_file_source_handler_returns_gone() -> None:
    handler = getattr(create_file_source, "__wrapped__", create_file_source)
    with pytest.raises(HTTPException) as exc:
        await handler(
            request=None,
            corpus_uuid="kb-1",
            tenant=None,
            facade=None,
            current_user=None,
            file=None,
        )

    assert exc.value.status_code == 410


def test_legacy_claim_extractor_runtime_switch_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "apps.knowledge.service.knowledge_facade.settings",
        SimpleNamespace(CLAIM_EXTRACTOR_VERSION="legacy"),
    )

    assert KnowledgeFacade._claim_extractor_version() == "v1"
