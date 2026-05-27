from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent          # .../app
WORKSPACE_DIR = PROJECT_DIR.parent    # .../软考


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_model: str = "dashscope/qwen-plus"
    essay_grader_model: str = "dashscope/qwen-plus"
    embedding_model: str = "dashscope/text-embedding-v3"
    embedding_dim: int = 1024

    dashscope_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Runtime
    host: str = "127.0.0.1"
    port: int = 8765
    db_path: str = "data/ruankao.db"

    # Source data paths (relative to app/ directory)
    notes_dir: str = "../notes"
    textbook_txt: str = "../系统规划与管理师教程第2版.txt"
    consolidated_notes: str = "../系统规划与管理师_全书结构化笔记.md"

    @property
    def db_file(self) -> Path:
        p = Path(self.db_path)
        return p if p.is_absolute() else (PROJECT_DIR / p)

    @property
    def notes_path(self) -> Path:
        p = Path(self.notes_dir)
        return p if p.is_absolute() else (PROJECT_DIR / p)

    @property
    def textbook_txt_path(self) -> Path:
        p = Path(self.textbook_txt)
        return p if p.is_absolute() else (PROJECT_DIR / p)

    @property
    def consolidated_notes_path(self) -> Path:
        p = Path(self.consolidated_notes)
        return p if p.is_absolute() else (PROJECT_DIR / p)


settings = Settings()
