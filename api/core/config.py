from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://devenv:devenv@localhost:5432/devenv"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    data_dir: str = "data"

    # Global defaults applied when a user has no per-user override set
    # (see api/models/user.py). No admin surface exists yet to edit those
    # overrides; they'd be set directly in the database until that lands.
    default_max_environments: int = 3
    default_cpu_limit: float = 0.5
    default_mem_limit_mb: int = 512


settings = Settings()
