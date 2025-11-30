from .base import BaseConfig


class DevConfig(BaseConfig):
    QDRANT_URL: str
    QDRANT_API_KEY: str
    OPENAI_API_KEY: str

    api_port: int = 8010
    # dev-specifikus override-ok
