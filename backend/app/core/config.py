from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/open_city_map")
    cors_origins: str = "http://localhost:3000,http://localhost:3001"
    cors_origin_regex: str | None = None
    log_level: str = "INFO"
    app_environment: str = "development"
    app_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"
    jwt_secret_key: str = "development-only-change-me-32-bytes-minimum"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    refresh_token_reuse_grace_seconds: int = 5
    refresh_rate_limit_attempts: int = 30
    refresh_rate_limit_window_seconds: int = 60
    email_verification_expire_hours: int = 24
    password_reset_expire_minutes: int = 60
    auth_access_cookie_name: str = "ocm_access_token"
    auth_refresh_cookie_name: str = "ocm_refresh_token"
    auth_csrf_cookie_name: str = "ocm_csrf_token"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"
    auth_cookie_domain: str | None = None
    auth_cookie_path: str = "/"
    email_backend: str = "console"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "noreply@example.org"
    smtp_from_name: str = "OK Lab Flensburg"
    smtp_use_tls: bool = True
    contact_to_email: str | None = None
    contact_to_name: str = "Stadtplaner / OK Lab Flensburg"
    contact_form_token_expire_minutes: int = 30
    contact_form_min_seconds: int = 2
    contact_ip_rate_limit_attempts: int = 5
    contact_email_rate_limit_attempts: int = 3
    contact_rate_limit_window_seconds: int = 3600
    contact_turnstile_enabled: bool = False
    turnstile_site_key: str | None = None
    turnstile_secret_key: str | None = None
    github_client_id: str | None = None
    github_client_secret: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    oauth_redirect_base_url: str | None = None
    auth_rate_limit_attempts: int = 8
    auth_rate_limit_window_seconds: int = 300
    avatar_upload_dir: str = "data/uploads"
    avatar_max_file_size: int = 5_242_880
    avatar_output_size: int = 512
    avatar_webp_quality: int = 85
    media_base_url: str = ""
    nominatim_base_url: str | None = None
    nominatim_user_agent: str = "OpenCityMap/0.1"
    nominatim_email: str | None = None
    nominatim_timeout_seconds: float = 5.0
    nominatim_cache_ttl_seconds: int = 86_400
    osm_external_fallback_enabled: bool = False
    overpass_api_url: str | None = None
    overpass_user_agent: str = "Stadtplaner/0.1 (https://Stadtplaner.oklabflensburg.de)"
    overpass_timeout_seconds: float = 8.0
    osm_lookup_cache_ttl_seconds: int = 3_600
    osm_external_min_interval_seconds: float = 1.0
    osm_lookup_max_matches: int = 25

    # Resolve the backend environment independently of the process working directory.
    model_config = SettingsConfigDict(env_file=BACKEND_ENV_FILE, env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def production(self) -> bool:
        return self.app_environment.lower() == "production"

    def validate_security(self) -> None:
        if self.production and self.jwt_secret_key == "development-only-change-me-32-bytes-minimum":
            raise RuntimeError("JWT_SECRET_KEY must be configured in production")
        if self.production and not self.auth_cookie_secure:
            raise RuntimeError("AUTH_COOKIE_SECURE must be true in production")
        if self.contact_turnstile_enabled and (
            not self.turnstile_site_key or not self.turnstile_secret_key
        ):
            raise RuntimeError("Turnstile site and secret keys must be configured when enabled")

    @property
    def configured_oauth_providers(self) -> list[str]:
        providers: list[str] = []
        if self.github_client_id and self.github_client_secret:
            providers.append("github")
        if self.google_client_id and self.google_client_secret:
            providers.append("google")
        return providers


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_security()
    return settings
