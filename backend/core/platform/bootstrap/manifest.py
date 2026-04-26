from __future__ import annotations

from typing import Callable

from core.capabilities.cache.redis_client import close_redis
from core.kernel.config import app_settings
from core.platform.manifest import AppManifest

# ---------------------------------------------------------------------------
# Pluggable app-modules loader
# ---------------------------------------------------------------------------
# Platform code never imports application modules directly. The composition
# root calls `configure_app_modules_loader` once at startup to inject the
# callable that returns the active AppModule instances. When not configured
# (e.g. platform-only mode or unit tests) the platform starts with an empty
# module set, which is the correct default.
# ---------------------------------------------------------------------------

_app_modules_loader: Callable[[], tuple] | None = None


def configure_app_modules_loader(loader: Callable[[], tuple]) -> None:
    """Register the callable that provides app-level AppModule instances.

    Must be called before the first call to ``load_app_manifest()`` – ideally
    at the very top of the composition-root entry point (``main.py``).
    """
    global _app_modules_loader
    _app_modules_loader = loader


def _resolve_app_modules() -> tuple:
    """Return the registered app modules, or an empty tuple when none are configured."""
    if _app_modules_loader is None:
        return ()
    return _app_modules_loader()


# ---------------------------------------------------------------------------
# Bootstrap / shutdown hook factories
# ---------------------------------------------------------------------------


def _make_bootstrap_hook(manifest_loader: Callable[[], AppManifest]) -> Callable:
    def _bootstrap_runtime_graph() -> None:
        from core.kernel.bootstrap.container import get_container

        container = get_container(manifest_loader)
        container.initialize_runtime_storage()
        container.start_runtime_services()

    return _bootstrap_runtime_graph


def _make_shutdown_hook(manifest_loader: Callable[[], AppManifest]) -> Callable:
    async def _platform_shutdown(app) -> None:
        from core.kernel.bootstrap.container import get_container

        container = get_container(manifest_loader)
        try:
            container.shutdown()
        finally:
            close_redis()

    return _platform_shutdown


# ---------------------------------------------------------------------------
# Manifest factories
# ---------------------------------------------------------------------------


def load_platform_only_app_manifest() -> AppManifest:
    """Manifest without any app modules – used for platform-only startup or tests."""

    def _this_manifest_loader() -> AppManifest:
        return load_platform_only_app_manifest()

    return AppManifest(
        app_name=app_settings.app_name,
        description=app_settings.app_description,
        version=app_settings.app_version,
        bootstrap_hooks=(_make_bootstrap_hook(_this_manifest_loader),),
        app_modules=(),
        shutdown_hooks=(_make_shutdown_hook(_this_manifest_loader),),
    )


def make_app_manifest_loader(
    *,
    app_modules_loader: Callable[[], tuple] | None = None,
) -> Callable[[], AppManifest]:
    """Return a zero-arg callable → AppManifest, suitable for ``AppContainer``.

    The returned loader is stable by identity, so it works correctly with the
    ``@lru_cache`` on ``get_container``.
    """
    _effective_loader = app_modules_loader or _resolve_app_modules

    def _loader() -> AppManifest:
        return AppManifest(
            app_name=app_settings.app_name,
            description=app_settings.app_description,
            version=app_settings.app_version,
            app_modules=_effective_loader(),
        )

    return _loader


def load_app_manifest() -> AppManifest:
    """Build the full app manifest, wiring app modules via the registered loader.

    This function is intentionally zero-arg so it can be passed directly to
    ``get_container`` (which uses it as an ``lru_cache`` key).  App modules are
    resolved through ``_resolve_app_modules`` which delegates to the loader
    registered via ``configure_app_modules_loader``.
    """
    _manifest_loader = make_app_manifest_loader()
    return AppManifest(
        app_name=app_settings.app_name,
        description=app_settings.app_description,
        version=app_settings.app_version,
        bootstrap_hooks=(_make_bootstrap_hook(_manifest_loader),),
        app_modules=_resolve_app_modules(),
        shutdown_hooks=(_make_shutdown_hook(_manifest_loader),),
    )
