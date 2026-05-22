# backend/core/kernel/app/__init__.py
# Feladat: Az app alkönyvtár publikus importfelületét adja. Közvetlenül exportálja az AppManifestet, a FastAPI app factoryt pedig lazy importtal teszi elérhetővé, hogy a csomag importja ne húzza be azonnal a teljes FastAPI runtime-ot. Ezt külső kernel-fogyasztók és tesztek használhatják stabil, rövid belépési pontként.
# Sárközi Mihály - 2026.05.21

from core.kernel.app.app_manifest import AppManifest


def __getattr__(name: str) -> object:
    if name == "create_app_from_manifest":
        from core.kernel.app.app_factory import create_app_from_manifest

        return create_app_from_manifest
    raise AttributeError(name)


__all__ = ["AppManifest", "create_app_from_manifest"]
