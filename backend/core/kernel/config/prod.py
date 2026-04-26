# Az éles(prod) környezet beállításai amik felülírják a base config-ot vagy .env file-t
# 2026.02.14 - Sárközi Mihály

from .base import BaseConfig

class ProdConfig(BaseConfig):
    # prod override-ok (pl. csak HTTPS URL-ek, más DSN)
    pass
