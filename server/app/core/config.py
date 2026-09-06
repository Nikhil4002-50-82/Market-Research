from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./synth_research.db"
    gemini_api_key: str = "dummy_gemini_api_key"
    gemini_model: str = "gemini-3.6-flash"
    langchain_tracing_v2: bool = False
    langchain_api_key: str | None = None
    langchain_project: str = "synth-research-dev"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
