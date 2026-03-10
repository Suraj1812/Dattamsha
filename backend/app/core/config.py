from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Dattamsha HR Intelligence API"
    environment: Literal["dev", "test", "staging", "prod"] = "dev"
    database_url: str = "sqlite:///./dattamsha.db"
    nudge_threshold_attrition: float = 0.65
    nudge_threshold_burnout: float = 0.70
    policy_doc_path: str = "./policies/policies.md"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    allowed_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]
    trusted_hosts: Annotated[list[str], NoDecode] = ["*"]
    default_user_role: Literal["admin", "hr_admin", "manager", "analyst", "employee"] = "admin"
    require_authentication: bool = False
    api_key_role: Literal["admin", "hr_admin", "manager", "analyst", "employee"] = "admin"
    require_api_key: bool = False
    api_key: str = "change-me-in-production"
    auth_jwt_secret: str = "change-this-auth-secret"
    auth_access_token_minutes: int = 30
    auth_refresh_token_days: int = 14
    auth_jwt_issuer: str = "dattamsha-api"
    auth_jwt_audience: str = "dattamsha-clients"
    auth_allow_self_signup: bool = False
    bootstrap_admin_email: str | None = "admin@dattamsha.local"
    bootstrap_admin_full_name: str = "Platform Admin"
    bootstrap_admin_password: str | None = "ChangeMe@123"
    enforce_nudge_consent: bool = False
    rate_limit_per_minute: int = 120
    enable_docs: bool = True
    auto_create_schema: bool = True
    response_compression_min_size: int = 1024
    snapshot_refresh_batch_size: int = 5000
    nudge_generation_batch_size: int = 10000
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle_seconds: int = 1800

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("allowed_origins", "trusted_hosts", mode="before")
    @classmethod
    def parse_comma_separated_lists(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("nudge_threshold_attrition", "nudge_threshold_burnout")
    @classmethod
    def validate_thresholds(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("thresholds must be between 0 and 1")
        return value

    @field_validator(
        "rate_limit_per_minute",
        "response_compression_min_size",
        "snapshot_refresh_batch_size",
        "nudge_generation_batch_size",
        "auth_access_token_minutes",
        "auth_refresh_token_days",
    )
    @classmethod
    def validate_positive_ints(cls, value: int) -> int:
        if value < 1:
            raise ValueError("value must be >= 1")
        return value

    @field_validator("db_pool_size", "db_max_overflow", "db_pool_recycle_seconds")
    @classmethod
    def validate_non_negative_ints(cls, value: int) -> int:
        if value < 0:
            raise ValueError("value must be >= 0")
        return value

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.environment == "prod":
            if self.enable_docs:
                raise ValueError("enable_docs must be false in prod")
            if not self.require_authentication:
                raise ValueError("require_authentication must be true in prod")
            if self.auth_jwt_secret == "change-this-auth-secret":
                raise ValueError("auth_jwt_secret must be changed in prod")
            if self.require_api_key and self.api_key == "change-me-in-production":
                raise ValueError("api_key must be changed when require_api_key is true in prod")
            if self.bootstrap_admin_password == "ChangeMe@123":
                raise ValueError("bootstrap_admin_password must be changed in prod")
            if self.auto_create_schema:
                raise ValueError("auto_create_schema must be false in prod")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
