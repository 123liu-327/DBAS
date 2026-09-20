from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "宿舍账单分摊管家"
    api_prefix: str = "/api"
    data_dir: Path = PROJECT_ROOT / "data"
    seed_demo_books: bool = True

    model_config = SettingsConfigDict(
        env_prefix="DORMBILL_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
