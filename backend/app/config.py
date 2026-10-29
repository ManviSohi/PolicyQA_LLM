from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    app_env: str = "development"
    frontend_origin: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173,http://localhost:8080"
    )
    database_url: str = ""
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "policy_intelligence"
    postgres_user: str = "policy_app"
    postgres_password: str = ""
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def require_postgresql_runtime(self) -> "Settings":
        if not self.database_url:
            if not self.postgres_password:
                raise ValueError("Set DATABASE_URL or POSTGRES_PASSWORD for PostgreSQL.")
            self.database_url = URL.create(
                "postgresql+psycopg",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                database=self.postgres_db,
            ).render_as_string(hide_password=False)

        backend = make_url(self.database_url).get_backend_name()
        if backend != "postgresql" and self.app_env != "test":
            raise ValueError("DATABASE_URL must use PostgreSQL outside the test environment.")
        return self


settings = Settings()
