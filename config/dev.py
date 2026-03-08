# A dev környezet beállításai amik felülírják a base config-ot vagy .env file-t
# 2026.02.14 - Sárközi Mihály

from .base import BaseConfig

class DevConfig(BaseConfig):
    QDRANT_URL: str
    QDRANT_API_KEY: str
    OPENAI_API_KEY: str

    api_port: int = 8010
    database_pool_pre_ping: bool = False  # dev: gyorsabb első kérés (nincs extra ping round-trip)
    cookie_secure: bool = False  # HTTP (demo.local:5173) mellett a cookie csak Secure=False-ként tárolódik
