# Egy helyen töltjük a projekt .env-jét és értelmezzük az APP_ENV-et.
# Devben a DevConfig adhat kényelmes fallbackeket, prodban csak env-alapú, szigorú config engedett.
# 2026.02.14 - Sárközi Mihály

from functools import lru_cache

from .dev import DevConfig
from .environment import get_app_env, load_project_env
from .prod import ProdConfig

# Ez a függvény betölti a(z) konfiguráció logikáját.
@lru_cache(maxsize=1)
def load_config():
    load_project_env()
    env = get_app_env()
    return ProdConfig() if env == "prod" else DevConfig()
