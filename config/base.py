from pydantic_settings import BaseSettings


class BaseConfig(BaseSettings):
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8010

    # DB
    mysql_dsn: str = "mysql+pymysql://root:Misi2010@localhost:3306/aiplaza"

    # LLM
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"

    # Auth/JWT
    jwt_secret: str = "change_me"
    access_ttl_min: int = 15
    refresh_ttl_days: int = 14

    class Config:
        env_prefix = ""  # opcionális: pl. “APP_”
        case_sensitive = False
