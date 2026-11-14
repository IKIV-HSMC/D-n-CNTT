from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import json


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:changeme@localhost:5432/docmind"

    # File upload
    MAX_UPLOAD_MB: int = 20
    STORAGE_PATH: str = "/storage/uploads"

    # CORS – lưu dưới dạng JSON string trong .env, parse thành list
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # ── Ollama / AI model ─────────────────────────────────────────────────────
    # Host nơi Ollama đang chạy (mặc định local)
    OLLAMA_HOST: str = "http://localhost:11434"
    # Tên model đã import vào Ollama (xem hướng dẫn bên dưới)
    OLLAMA_MODEL: str = "mindmap-model"
    # Timeout (giây) cho mỗi lần gọi Ollama
    OLLAMA_TIMEOUT: float = 120.0

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024


settings = Settings()
