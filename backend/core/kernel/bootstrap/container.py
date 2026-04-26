from __future__ import annotations

from functools import lru_cache

from core.platform.runtime.app_container import AppContainer


def _default_manifest_loader():
    from core.platform.bootstrap.manifest import load_app_manifest

    return load_app_manifest


@lru_cache(maxsize=None)
def get_container(manifest_loader=None) -> AppContainer:
    if manifest_loader is None:
        manifest_loader = _default_manifest_loader()
    return AppContainer(manifest_loader)


class _LazyContainerProxy:
    def __getattr__(self, name):
        return getattr(get_container(), name)


container = _LazyContainerProxy()

__all__ = ["get_container", "container"]
