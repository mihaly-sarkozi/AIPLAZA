from __future__ import annotations

from functools import lru_cache
from threading import RLock

from core.platform.runtime.app_container import AppContainer

_container_build_lock = RLock()


def _default_manifest_loader():
    from core.platform.bootstrap.manifest import load_app_manifest

    return load_app_manifest


@lru_cache(maxsize=None)
def _build_container(manifest_loader) -> AppContainer:
    return AppContainer(manifest_loader)


def get_container(manifest_loader=None) -> AppContainer:
    if manifest_loader is None:
        manifest_loader = _default_manifest_loader()
    # Több párhuzamos kérés ugyanazon cold-start alatt ne építsen külön konténert.
    with _container_build_lock:
        return _build_container(manifest_loader)


class _LazyContainerProxy:
    def __getattr__(self, name):
        return getattr(get_container(), name)


container = _LazyContainerProxy()

__all__ = ["get_container", "container"]
