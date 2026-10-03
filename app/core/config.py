from typing import Literal, Optional
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


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
    tutor_enabled: bool = False
    tutor_enable_thinking: Optional[bool] = None
    tutor_reasoning_effort: Optional[Literal['low', 'medium', 'high']] = None
    tutor_temperature: float = Field(default=0.2, ge=0, le=2)
    tutor_max_tokens: int = Field(default=1536, ge=256, le=4096)
    tutor_read_timeout: int = Field(default=45, ge=10, le=45)
    engagement_enabled: bool = False
    reading_test_threshold: int = Field(default=75, ge=1, le=100)
    content_pipeline_enabled: bool = False
    automatic_lessons_enabled: bool = False
    tiered_tests_enabled: bool = False
    lesson_generations_per_day: int = Field(default=12, ge=1, le=100)
    lesson_requests_per_user_day: int = Field(default=6, ge=1, le=30)
    content_api_base_url: Optional[str] = None
    content_provider: str = 'openai-compatible'
    content_output_mode: str = 'json_object'
    content_model: Optional[str] = None
    content_stream: bool = False
    content_max_tokens: int = Field(default=6000, ge=1, le=32768)
    content_read_timeout: int = Field(default=90, ge=10, le=600)
    content_temperature: Optional[float] = Field(default=None, ge=0, le=2)
    content_top_p: Optional[float] = Field(default=None, gt=0, le=1)
    content_enable_thinking: Optional[bool] = None
    content_reasoning_effort: Optional[Literal['low', 'medium', 'high']] = None

    @property
    def content_request_options(self) -> dict:
        thinking = self.content_enable_thinking
        if thinking is None and self.content_provider == 'openai-compatible' and urlsplit(self.content_api_base_url or '').hostname == 'integrate.api.nvidia.com':
            thinking = False
        return {
            'max_tokens': self.content_max_tokens, 'stream': self.content_stream,
            'read_timeout': self.content_read_timeout,
            'temperature': self.content_temperature, 'top_p': self.content_top_p,
            'enable_thinking': thinking,
            'reasoning_effort': self.content_reasoning_effort,
        }

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
