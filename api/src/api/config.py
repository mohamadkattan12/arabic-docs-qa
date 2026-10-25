from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # .env lives at the repo root; api/ is the working directory when run outside Docker.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    anthropic_api_key: SecretStr | None = None
    database_url: str = "postgresql://postgres:postgres@localhost:5432/docsqa"
    web_origin: str = "http://localhost:3000"
    # Recommended by the eval (2026-10-25T15-22-18Z): ties Opus 5.5 at half the cost.
    answer_model: str = "claude-sonnet-5-5"
    judge_model: str = "claude-sonnet-5-5"
    embedding_model: str = "intfloat/multilingual-e5-large"
    corpus_dir: str = "../corpus"
    eval_results_dir: str = "eval/results"
    # "vector" won 10/10 vs 6/10 for "hybrid" on cross-language questions (see plan.md, step 5).
    retrieval_mode: Literal["vector", "hybrid"] = "vector"

    @field_validator("anthropic_api_key", mode="before")
    @classmethod
    def empty_key_is_unset(cls, value: object) -> object:
        # `.env.example` ships `ANTHROPIC_API_KEY=` with no value.
        return None if isinstance(value, str) and not value.strip() else value


settings = Settings()
