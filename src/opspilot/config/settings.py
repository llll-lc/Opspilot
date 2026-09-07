"""仅定义类型化配置；功能开关不会启用尚未实现的能力。"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """运行时配置；密钥必须保留在版本控制之外。"""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="OPSPILOT_", extra="ignore", frozen=True
    )

    application_name: str = "OpsPilot API"
    application_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    api_v1_prefix: str = "/api/v1"
    docs_enabled: bool = True

    deepseek_api_key: SecretStr | None = Field(default=None, validation_alias="DEEPSEEK_API_KEY")
    deepseek_base_url: HttpUrl = Field(
        default=HttpUrl("https://api.deepseek.com"), validation_alias="DEEPSEEK_BASE_URL"
    )
    deepseek_model: str = Field(default="deepseek-v4-flash", validation_alias="DEEPSEEK_MODEL")
    llm_timeout_seconds: int = Field(
        default=30, ge=1, le=300, validation_alias="LLM_TIMEOUT_SECONDS"
    )
    llm_max_retries: int = Field(default=2, ge=0, le=5, validation_alias="LLM_MAX_RETRIES")

    embedding_model_path: str | None = Field(default=None, validation_alias="EMBEDDING_MODEL_PATH")
    reranker_model_path: str | None = Field(default=None, validation_alias="RERANKER_MODEL_PATH")
    model_device: Literal["cpu"] = Field(default="cpu", validation_alias="MODEL_DEVICE")
    model_inference_concurrency: int = Field(
        default=1, ge=1, le=1, validation_alias="MODEL_INFERENCE_CONCURRENCY"
    )

    database_url: SecretStr | None = Field(default=None, validation_alias="DATABASE_URL")
    auth_token_secret: SecretStr | None = Field(
        default=None, validation_alias="OPSPILOT_SECURITY_AUTH_TOKEN_SECRET"
    )
    auth_token_issuer: str = Field(
        default="opspilot-local", validation_alias="OPSPILOT_SECURITY_AUTH_TOKEN_ISSUER"
    )
    auth_token_audience: str = Field(
        default="opspilot-api", validation_alias="OPSPILOT_SECURITY_AUTH_TOKEN_AUDIENCE"
    )
    superset_base_url: HttpUrl | None = Field(default=None, validation_alias="SUPERSET_BASE_URL")
    superset_mcp_url: HttpUrl | None = Field(default=None, validation_alias="SUPERSET_MCP_URL")

    skills_enabled: bool = Field(default=False, validation_alias="SKILLS_ENABLED")
    superset_mcp_enabled: bool = Field(default=False, validation_alias="SUPERSET_MCP_ENABLED")
    specialists_enabled: bool = Field(default=False, validation_alias="SPECIALISTS_ENABLED")


@lru_cache
def get_settings() -> Settings:
    """为每个进程返回一个不可变的配置快照。"""
    return Settings()
