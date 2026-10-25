from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:5432/docsqa"
    web_origin: str = "http://localhost:3000"
    answer_model: str = "claude-opus-5-5"
    judge_model: str = "claude-sonnet-5-5"
    embedding_model: str = "intfloat/multilingual-e5-large"
    # Must match embedding_model (e5-large: 1024, MiniLM-L12: 384).
    embedding_dim: int = 1024


settings = Settings()
