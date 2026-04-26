# Ez a fájl az alkalmazás fő backend belépési pontját és app indítását tartalmazza.
# Composition root: ez az egyetlen pont ahol az apps/ és a core/platform/ találkoznak.
from apps import load_enabled_app_modules
from core.platform.bootstrap.manifest import configure_app_modules_loader, load_app_manifest
from core.kernel.app_factory import create_app_from_manifests
from core.platform.registry import load_core_platform_manifest

# Regisztrálja az app-modulok betöltőjét, mielőtt bármi mást csinálnánk.
# Ettől kezdve a platform réteg képes betölteni az app modulokat anélkül,
# hogy közvetlen importja lenne az apps/ csomagra.
configure_app_modules_loader(load_enabled_app_modules)

app = create_app_from_manifests(load_core_platform_manifest(), load_app_manifest())
