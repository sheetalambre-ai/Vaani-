from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    GROQ_API_KEY: Optional[str] = None
    GROQ_LLM_MODEL: Optional[str] = None

    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: Optional[str] = None
    GEMINI_EMBED_MODEL: Optional[str] = None

    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: Optional[str] = None

    TRACKER: str = "mock"
    TRELLO_KEY: Optional[str] = None
    TRELLO_TOKEN: Optional[str] = None
    TRELLO_LIST_ID: Optional[str] = None
    GITHUB_TOKEN: Optional[str] = None
    GITHUB_REPO: Optional[str] = None

    TELEGRAM_BOT_TOKEN: Optional[str] = None

    DATABASE_URL: str = "sqlite+aiosqlite:///./vaanimanthan.db"

settings = Settings()
