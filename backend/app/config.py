from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration derived from environment variables."""

    deepseek_api_key: str = Field(..., env="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        description="Override to point at a proxy or self-hosted gateway.",
        env="DEEPSEEK_BASE_URL",
    )
    app_name: str = "AI Agent Backend"
    data_dir: Path = Field(
        default=Path("./data"),
        description="Base directory for persisted data (vector store, uploads, sqlite).",
    )
    sqlite_path: Path = Field(
        default=Path("./data/agent.db"),
        description="SQLite database path for metadata.",
    )
    chroma_dir: Path = Field(
        default=Path("./data/chroma"),
        description="Chroma persistent directory.",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @field_validator("data_dir", "sqlite_path", "chroma_dir", mode="before")
    def resolve_path(cls, value: str | Path) -> Path:
        """Resolve relative paths against backend directory for consistency."""
        path = Path(value)
        if not path.is_absolute():
            backend_root = Path(__file__).resolve().parents[1]  # backend/ directory
            path = (backend_root / path).resolve()
        return path


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
