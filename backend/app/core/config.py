from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Lead Hunter"
    debug: bool = True
    database_url: str = "sqlite+aiosqlite:///./upwork_jobs.db"

    # AI (Groq)
    groq_api_key: str = ""
    # NOTE: llama-3.1-70b-versatile was decommissioned by Groq.
    # Use a currently-supported model. See https://console.groq.com/docs/models
    groq_model: str = "llama-3.3-70b-versatile"

    # Scraper settings
    scrape_delay_min: float = 2.0
    scrape_delay_max: float = 5.0
    max_retries: int = 3
    scraper_headless: bool = True

    # Upwork settings
    upwork_base_url: str = "https://www.upwork.com"

    # Pydantic-settings v2 config. extra="ignore" so unknown .env keys don't crash startup.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
