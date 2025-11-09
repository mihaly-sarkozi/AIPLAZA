from .base import BaseConfig


class DevConfig(BaseConfig):
    api_port: int = 8010
    # dev-specifikus override-ok
