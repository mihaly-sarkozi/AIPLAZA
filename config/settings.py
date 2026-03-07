# Betölti a beállítokat tartalmazo fileokat.
# 2026.02.14 - Sárközi Mihály

from functools import lru_cache
from config.loader import load_settings


@lru_cache(maxsize=1)
def _get():
    return load_settings()


settings = _get()
