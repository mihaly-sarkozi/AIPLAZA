"""Manifest merge: core platform manifest + alkalmazás manifest."""
from __future__ import annotations

from collections.abc import Callable

from core.platform.manifest import AppManifest, PlatformManifest, merge_app_manifest
from core.platform.registry import load_core_platform_manifest


def load_merged_manifest(manifest_loader: Callable[[], AppManifest]) -> PlatformManifest:
    """Betölti a core platform modulokat, meghívja az app manifest loader-t, összefésüli."""
    platform_manifest = load_core_platform_manifest()
    app_manifest = manifest_loader()
    return merge_app_manifest(platform_manifest, app_manifest)
