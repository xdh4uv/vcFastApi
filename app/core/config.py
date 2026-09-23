from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    database_url_unpooled: Optional[str] = None
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    google_client_id: Optional[str] = None
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
    cors_origin_regex: str = r"https://([a-z0-9-]+\.)?vercel\.app"
    uploads_dir: str = "uploads"
    content_api_key: Optional[str] = None
    content_pipeline_enabled: bool = False
    content_api_base_url: Optional[str] = None
    content_provider: str = 'openai-compatible'
    content_output_mode: str = 'json_object'
    content_model: Optional[str] = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
