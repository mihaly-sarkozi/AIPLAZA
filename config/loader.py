from functools import lru_cache
from .dev import DevConfig
from .prod import ProdConfig
import os


@lru_cache(maxsize=1)
def load_settings():
    env = os.getenv("APP_ENV", "dev").lower()
    return ProdConfig() if env == "prod" else DevConfig()
