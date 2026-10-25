from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:5432/docsqa"
    web_origin: str = "http://localhost:3000"
    answer_model: str = "claude-opus-5-5"
    judge_model: str = "claude-sonnet-5-5"
    embedding_model: str = "intfloat/multilingual-e5-large"
    corpus_dir: str = "../corpus"
    # "vector" won 10/10 vs 6/10 for "hybrid" on cross-language questions (see plan.md, step 5).
    retrieval_mode: Literal["vector", "hybrid"] = "vector"


settings = Settings()
