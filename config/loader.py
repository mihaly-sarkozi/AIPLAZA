# Egy helyen töltjük a .env-t: itt. 
# Így az APP_ENV és minden más változó elérhető.
# Attól függően hogy fejlesztő, vagy éles környezetben vagyunk úgy tölti be a config fileokat.
# 2026.02.14 - Sárközi Mihály

from pathlib import Path
import os
from functools import lru_cache

from dotenv import load_dotenv

from .dev import DevConfig
from .prod import ProdConfig




_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)


@lru_cache(maxsize=1)
def load_settings():
    env = os.getenv("APP_ENV", "dev").lower()
    return ProdConfig() if env == "prod" else DevConfig()
