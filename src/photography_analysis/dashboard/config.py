from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    data_cache_dir: str = "./data"
    photos_dir: str
    immich_host: str
    immich_api_key: str
    redis_url: str | None = None

    class Config:
        env_file = ".env"


settings = Settings()
