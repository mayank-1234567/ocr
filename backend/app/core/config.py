from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Universal Chess Tactics Trainer"
    db_url: str = "sqlite:///./storage/trainer.db"
    storage_root: Path = Path("./storage")
    uploads_dir: Path = Path("./storage/uploads")
    artifacts_dir: Path = Path("./storage/artifacts")
    stockfish_path: str | None = None
    engine_depth: int = 14

    model_config = SettingsConfigDict(env_prefix="UCT_", env_file=".env", extra="ignore")


settings = Settings()
