"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings sourced from environment / .env file."""

    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-oss-120b"
    port: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
