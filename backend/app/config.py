import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "antigravity_dev_secret_key_32bytes_sample!"
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "sqlite:///./woocommerce_analytics.db"

    # WooCommerce
    WC_STORE_URL: str = "https://demo-store.local"
    WC_CONSUMER_KEY: str = "ck_sample_key"
    WC_CONSUMER_SECRET: str = "cs_sample_secret"
    WC_API_VERSION: str = "wc/v3"
    WC_VERIFY_SSL: bool = True
    WC_TIMEOUT_SECONDS: int = 30
    WC_MAX_RETRIES: int = 3

    # Regional Defaults
    DEFAULT_CURRENCY: str = "USD"
    DEFAULT_TIMEZONE: str = "UTC"

    # AI Configuration
    LLM_PROVIDER: str = "mock"  # mock, openai, gemini, anthropic
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    AI_MODEL_NAME: str = "mock-analyst-v1"

    # Ports
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    STREAMLIT_PORT: int = 8501

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
