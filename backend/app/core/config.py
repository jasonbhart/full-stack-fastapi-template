import secrets
import warnings
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    AnyUrl,
    BeforeValidator,
    EmailStr,
    HttpUrl,
    PostgresDsn,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource
from typing_extensions import Self


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class AppEnv(str, Enum):
    """Application environment enum for environment-specific configuration."""

    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


def normalize_app_env_value(value: Any) -> str | None:
    """
    Normalize APP_ENV value from various formats to a valid environment string.

    Handles:
    - AppEnv enum instances → .value
    - Enum string representations like "AppEnv.STAGING" → "staging"
    - Enum repr like "<AppEnv.STAGING: 'staging'>" → "staging"
    - Case-insensitive strings like "STAGING" → "staging"
    - Strings with whitespace like " staging " → "staging"

    Returns:
        Normalized environment string if valid, None otherwise.
    """
    if isinstance(value, AppEnv):
        return value.value

    if isinstance(value, str):
        # First, strip whitespace from both ends
        env_str = value.strip()

        # Then strip angle brackets and quotes
        env_str = env_str.strip("<>\"'")

        # Strip whitespace again (in case quotes/brackets enclosed spaces)
        env_str = env_str.strip()

        # If it contains a colon (repr format), take the part after the last colon
        # Use rsplit to handle multiple colons (e.g., "APP_ENV: <AppEnv.STAGING: 'staging'>")
        if ":" in env_str:
            env_str = env_str.rsplit(":", 1)[1].strip().strip("\"'").strip()

        # If it contains a dot (enum.VALUE or AppEnv.STAGING), take the part after the last dot
        if "." in env_str:
            env_str = env_str.split(".")[-1].strip()

        # Normalize to lowercase
        env_str_lower = env_str.lower()

        # Validate against AppEnv values using public API (forward-compatible)
        valid_values = {member.value for member in AppEnv}
        if env_str_lower in valid_values:
            return env_str_lower

    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    FRONTEND_HOST: str = "http://localhost:5173"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    # Application environment (using enum for better type safety)
    APP_ENV: AppEnv = AppEnv.LOCAL

    @field_validator("APP_ENV", mode="before")
    @classmethod
    def normalize_app_env(cls, v: Any) -> str | AppEnv:
        """Normalize APP_ENV input to handle various formats."""
        normalized = normalize_app_env_value(v)
        return normalized if normalized is not None else v

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return PostgresDsn.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: EmailStr | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    # LangChain/LangGraph Configuration
    LANGCHAIN_API_KEY: str | None = None
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_PROJECT: str | None = None
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"

    # LLM Model Configuration
    LLM_MODEL_NAME: str = "gpt-4"
    LLM_MODEL_PROVIDER: Literal["openai", "anthropic", "azure"] = "openai"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2048
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    AZURE_OPENAI_ENDPOINT: str | None = None
    AZURE_OPENAI_API_KEY: str | None = None
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"

    # Langfuse Observability Configuration
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    LANGFUSE_ENABLED: bool = False
    LANGFUSE_SAMPLE_RATE: float = 1.0  # Sample rate for traces (0.0 to 1.0)

    # Evaluation Configuration
    EVALUATION_API_KEY: str | None = None
    EVALUATION_BASE_URL: str = "https://api.openai.com/v1"
    EVALUATION_LLM: str = "gpt-4o-mini"
    EVALUATION_SLEEP_TIME: int = 1  # Sleep time between evaluations in seconds

    # Rate Limiting Configuration
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_DB: int = 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def REDIS_URL(self) -> str:
        """Construct Redis URL from components."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """
        Customize settings sources to support environment-specific .env files.

        Priority order (first = highest priority, last = lowest priority):
        1. Init settings (passed to __init__) - HIGHEST PRIORITY
        2. Environment variables
        3. File secrets (Docker secrets, runtime-mounted secrets at /run/secrets/<name>)
        4. Environment-specific .env file (../.env.local, ../.env.staging, or ../.env.production)
        5. Base .env file (../.env) - LOWEST PRIORITY
        """
        from pydantic_settings import DotEnvSettingsSource

        # Get the current environment from the settings sources in priority order
        # We need to check before the sources are fully merged, so query each source
        current_env = "local"  # Default fallback

        # Check sources in priority order: init_settings, env_settings, file_secret_settings, dotenv_settings
        for source in [init_settings, env_settings, file_secret_settings, dotenv_settings]:
            try:
                source_data = source()
                # Check for APP_ENV first (new field), then ENVIRONMENT (existing field)
                env_value = None
                if "APP_ENV" in source_data:
                    env_value = source_data["APP_ENV"]
                elif "ENVIRONMENT" in source_data:
                    env_value = source_data["ENVIRONMENT"]

                if env_value is not None:
                    # Use shared normalization helper
                    normalized = normalize_app_env_value(env_value)
                    if normalized is not None:
                        current_env = normalized
                        break
            except Exception:
                continue

        # Define the base directory (project root - one level above ./backend/)
        # __file__ is .../backend/app/core/config.py
        # We need to go up 4 levels: core -> app -> backend -> project_root
        base_dir = Path(__file__).parent.parent.parent.parent
        env_file_path = base_dir / f".env.{current_env}"

        # Create environment-specific dotenv source if the file exists
        env_specific_sources: list[PydanticBaseSettingsSource] = []
        if env_file_path.exists():
            # Extract config values from the settings class
            config = settings_cls.model_config
            env_specific_dotenv = DotEnvSettingsSource(
                settings_cls,
                env_file=env_file_path,
                env_file_encoding=config.get("env_file_encoding", "utf-8"),
                case_sensitive=config.get("case_sensitive"),
                env_prefix=config.get("env_prefix"),
                env_nested_delimiter=config.get("env_nested_delimiter"),
                env_ignore_empty=config.get("env_ignore_empty", True),
                env_parse_none_str=config.get("env_parse_none_str"),
                env_parse_enums=config.get("env_parse_enums"),
            )
            env_specific_sources.append(env_specific_dotenv)

        # Return sources in priority order (highest to lowest priority)
        return (
            init_settings,  # Arguments passed to Settings() - HIGHEST PRIORITY
            env_settings,  # Environment variables
            file_secret_settings,  # Docker secrets and runtime-mounted secrets
            *env_specific_sources,  # Environment-specific .env file
            dotenv_settings,  # Base .env file - LOWEST PRIORITY
        )

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )

        return self


settings = Settings()  # type: ignore
