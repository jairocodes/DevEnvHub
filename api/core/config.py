from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://devenv:devenv@localhost:5432/devenv"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    data_dir: str = "data"

    # Global defaults applied when a user has no per-user override set
    # (see api/models/user.py). Admins can set overrides via /admin endpoints.
    default_max_environments: int = 3
    default_cpu_limit: float = 0.5
    default_mem_limit_mb: int = 512

    # Comma-separated allowlist: a matching email is auto-promoted to admin
    # on its next login (see api/routers/auth.py). No API bootstraps this
    # further to keep the privilege-escalation surface small.
    admin_emails: str = ""

    @property
    def admin_email_list(self) -> list[str]:
        return [email.strip() for email in self.admin_emails.split(",") if email.strip()]


settings = Settings()
