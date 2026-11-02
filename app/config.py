from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Hiring Assessment API"
    environment: str = "development"
    database_url: str = "sqlite:///./hiring_assessment.db"
    sql_echo: bool = False
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_prompt_version: str = "v1"
    llm_max_attempts: int = 3
    candidate_link_secret: str = "development-candidate-link-secret"
    hr_mock_token: str = "development-hr-mock-token"
    upload_directory: str = "./uploads"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
