"""Configuración de la API, solo por variables de entorno (AGENTS.md, sección 5)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://caterin:caterin_dev@localhost:5433/caterin"

    jwt_secret: SecretStr = Field(default=SecretStr("dev-only-change-me-dev-only-change-me"))
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_days: int = 30
    login_max_attempts: int = 10
    login_window_min: int = 15
    refresh_cookie_secure: bool = True

    cors_origins: list[str] = ["http://localhost:5173"]
    storage_dir: Path = Path("/data")

    # Asistente (ADR-005). El umbral y el margen son PROVISIONALES: no están medidos, los calibra T10.
    assistant_router_threshold: float = 0.55
    assistant_router_margin: float = 0.10
    assistant_use_llm: bool = False  # nivel 1 apagado hasta validar la calidad de redacción en T10
    assistant_cache_size: int = 512
    # Nivel 2 (RAG sobre documentos). `k` y la similitud mínima son PROVISIONALES hasta T10.
    assistant_rag_k: int = 4
    assistant_rag_min_similarity: float = 0.45
    document_max_upload_mb: int = 10

    # Embeddings (ADR-003): bge-m3 servido por Ollama, 1024 dimensiones (fijas en la migración).
    embeddings_provider: Literal["ollama", "fake", "disabled"] = "ollama"
    embedding_model: str = "bge-m3"
    embedding_version: str = "bge-m3-ollama-1"  # cambiarla exige reindexar los documentos
    embedding_timeout_s: float = 30.0

    vision_model_path: Path = Path("/data/models/vision/model.onnx")  # junto a model.json
    vision_threshold: float = 0.5
    vision_max_image_mb: int = 15

    llm_provider: Literal["ollama", "fake", "disabled"] = "ollama"
    ollama_url: str = "http://ollama:11434"
    llm_model: str = "qwen3:4b"
    llm_timeout_s: float = 60.0
    # Portal de clientes (ADR-007): pedidos leídos con el LLM por cliente y hora (protege la CPU del servidor).
    portal_extract_per_hour: int = 10
    llm_keep_alive: str = "30m"

    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production() and settings.jwt_secret.get_secret_value().startswith("dev-only"):
        raise RuntimeError("JWT_SECRET no está configurado para producción")
    return settings
