from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
DEVELOPMENT_JWT_SECRET = "development-only-change-me-32-bytes-minimum"
DEVELOPMENT_OAUTH_STATE_SECRET = "development-oauth-state-change-me-32-bytes"
DEVELOPMENT_MFA_RECOVERY_PEPPER = "development-recovery-pepper-change-me-32-bytes"
MINIMUM_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    api_version: str = "0.2.0"
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/open_city_map"
    )
    cors_origins: str = "http://localhost:3000,http://localhost:3001"
    cors_origin_regex: str | None = None
    log_level: str = "INFO"
    app_environment: str = "development"
    app_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"
    jwt_secret_key: str = DEVELOPMENT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "http://localhost:8000"
    jwt_audience: str = "stadtplaner"
    oauth_state_secret: str = DEVELOPMENT_OAUTH_STATE_SECRET
    mfa_recovery_pepper: str = DEVELOPMENT_MFA_RECOVERY_PEPPER
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    refresh_token_reuse_grace_seconds: int = 5
    account_deletion_recent_auth_seconds: int = 600
    refresh_rate_limit_attempts: int = 30
    refresh_rate_limit_window_seconds: int = 60
    refresh_require_origin: bool = False
    email_verification_expire_hours: int = 24
    password_reset_expire_minutes: int = 60
    auth_access_cookie_name: str = "ocm_access_token"
    auth_refresh_cookie_name: str = "ocm_refresh_token"
    auth_csrf_cookie_name: str = "ocm_csrf_token"
    auth_mfa_cookie_name: str = "ocm_mfa_challenge"
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
    notification_retention_days: int = Field(default=90, ge=1)
    email_outbox_max_attempts: int = Field(default=8, ge=1, le=20)
    turnstile_site_key: str | None = None
    turnstile_secret_key: str | None = None
    github_client_id: str | None = None
    github_client_secret: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    oauth_redirect_base_url: str | None = None
    mastodon_sso_enabled: bool = False
    mastodon_sso_client_name: str = "Stadtplaner"
    mastodon_sso_default_instance: str = "https://norden.social"
    mastodon_sso_encryption_key: str | None = None
    mastodon_sso_timeout_seconds: float = 10.0
    mastodon_sso_state_ttl_seconds: int = 600
    mastodon_sso_registration_backoff_seconds: int = 300
    auth_rate_limit_attempts: int = 8
    auth_rate_limit_window_seconds: int = 300
    auth_rate_limit_backend: str = "memory"
    rate_limit_fail_closed: bool = False
    rate_limit_memory_max_keys: int = Field(default=10_000, ge=100, le=100_000)
    trusted_proxies: str = ""
    mfa_encryption_key: str | None = None
    mfa_challenge_expire_seconds: int = Field(default=300, ge=60, le=900)
    mfa_max_attempts: int = Field(default=5, ge=3, le=10)
    mfa_totp_issuer: str = "Stadtplaner - OK Lab Flensburg"
    mfa_totp_valid_window: int = Field(default=1, ge=0, le=1)
    mfa_recovery_code_count: int = Field(default=10, ge=8, le=20)
    mfa_setup_expire_seconds: int = Field(default=600, ge=300, le=1800)
    reauth_max_age_seconds: int = Field(default=600, ge=60, le=3600)
    require_mfa_for_superusers: bool = False
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "Stadtplaner OK Lab Flensburg"
    webauthn_origin: str = "http://localhost:3000"
    webauthn_challenge_expire_seconds: int = Field(default=300, ge=60, le=900)
    webauthn_timeout_ms: int = Field(default=60_000, ge=15_000, le=300_000)
    avatar_upload_dir: str = "data/uploads"
    avatar_max_file_size: int = 5_242_880
    upload_body_overhead_bytes: int = Field(default=65_536, ge=16_384, le=1_048_576)
    max_json_body_bytes: int = Field(default=2_097_152, ge=65_536, le=10_485_760)
    polygon_properties_max_bytes: int = Field(default=65_536, ge=1_024, le=1_048_576)
    public_query_timeout_ms: int = Field(default=8_000, ge=1_000, le=30_000)
    public_query_rate_limit_attempts: int = Field(default=120, ge=10, le=10_000)
    public_query_rate_limit_window_seconds: int = Field(default=60, ge=10, le=3_600)
    ai_search_enabled: bool = False
    ai_search_provider: str = "groq"
    ai_search_model: str | None = None
    openai_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_timeout_seconds: float = Field(default=8.0, ge=1.0, le=30.0)
    groq_max_retries: int = Field(default=1, ge=0, le=2)
    groq_temperature: float = Field(default=0.1, gt=0, le=2)
    assistant_query_logging: bool = False
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
    osm_viewport_feature_limit: int = 2_000
    osm_viewport_low_zoom_feature_limit: int = 800
    osm_viewport_mid_zoom_feature_limit: int = 1_200
    osm_viewport_point_feature_limit: int = 1_500
    osm_viewport_polygon_feature_limit: int = 350
    osm_viewport_building_feature_limit: int = 150
    osm_viewport_rate_limit_attempts: int = 180
    osm_viewport_rate_limit_window_seconds: int = 60
    redis_enabled: bool = False
    redis_required: bool = False
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_connect_timeout: float = 2.0
    redis_socket_timeout: float = 2.0
    redis_max_connections: int = 40
    cache_prefix: str = "stadtplaner:dev"
    cache_debug_headers: bool = False
    cache_lock_ttl_seconds: int = 15
    osm_viewport_cache_ttl: int = 1_800
    analytics_cache_ttl: int = 600
    analysis_area_cache_ttl: int = 3_600
    wikidata_api_url: str = "https://www.wikidata.org/w/api.php"
    wikidata_user_agent: str = (
        "Stadtplaner/1.0 (https://stadtplaner.oklabflensburg.de; OK Lab Flensburg)"
    )
    wikidata_timeout_seconds: float = 10.0
    wikidata_cache_ttl_seconds: int = 604_800
    wikidata_negative_cache_ttl_seconds: int = 86_400
    wikidata_stale_days: int = 90
    wikidata_search_limit: int = 8
    statistics_cache_ttl: int = 3_600
    flensburg_superset_base_url: str = "https://superset.flensburg.de"
    flensburg_superset_dashboard_id: str = "3b53ff0b-6e8c-435e-83f6-666f8a7cc158"
    flensburg_superset_timeout_seconds: float = 60.0
    polygon_cache_ttl: int = 60
    public_polygon_response_limit: int = Field(default=1_000, ge=10, le=10_000)
    comparable_cache_ttl: int = 600
    cache_payload_warning_bytes: int = 2_000_000
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout_seconds: float = 15.0
    database_health_timeout_seconds: float = Field(default=2.0, ge=0.25, le=10.0)
    mastodon_enabled: bool = False
    mastodon_base_url: str = "https://norden.social"
    mastodon_access_token: str | None = None
    mastodon_account_url: str = "https://norden.social/@oklabflensburg"
    mastodon_account_handle: str = "@oklabflensburg@norden.social"
    mastodon_default_visibility: str = "public"
    mastodon_area_updates_enabled: bool = True
    mastodon_area_update_debounce_seconds: int = 300
    mastodon_dry_run: bool = False
    mastodon_timeout_seconds: float = 10.0
    mastodon_hashtags: str = "Flensburg,OpenData,Stadtplaner"
    mastodon_max_attempts: int = 5
    mastodon_boundary_change_min_ratio: float = 0.01
    mastodon_screenshot_directory: str = "/data/stadtplaner-social"
    mastodon_screenshot_timeout_seconds: float = 30.0

    # Resolve the backend environment independently of the process working directory.
    model_config = SettingsConfigDict(env_file=BACKEND_ENV_FILE, env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()
        ]

    @property
    def production(self) -> bool:
        return self.app_environment.lower() == "production"

    @property
    def trusted_proxy_list(self) -> list[str]:
        return [value.strip() for value in self.trusted_proxies.split(",") if value.strip()]

    def validate_security(self) -> None:
        if self.production and (
            self.jwt_secret_key == DEVELOPMENT_JWT_SECRET
            or len(self.jwt_secret_key.strip()) < MINIMUM_JWT_SECRET_LENGTH
        ):
            raise RuntimeError(
                f"JWT_SECRET_KEY must be configured with at least "
                f"{MINIMUM_JWT_SECRET_LENGTH} characters in production"
            )
        if self.production and self.jwt_algorithm != "HS256":
            raise RuntimeError("JWT_ALGORITHM must be HS256")
        separated_secrets = {
            self.jwt_secret_key,
            self.oauth_state_secret,
            self.mfa_recovery_pepper,
        }
        if self.production and (
            len(self.oauth_state_secret.strip()) < MINIMUM_JWT_SECRET_LENGTH
            or self.oauth_state_secret == DEVELOPMENT_OAUTH_STATE_SECRET
        ):
            raise RuntimeError("OAUTH_STATE_SECRET must be configured securely in production")
        if self.production and (
            len(self.mfa_recovery_pepper.strip()) < MINIMUM_JWT_SECRET_LENGTH
            or self.mfa_recovery_pepper == DEVELOPMENT_MFA_RECOVERY_PEPPER
        ):
            raise RuntimeError("MFA_RECOVERY_PEPPER must be configured securely in production")
        if self.production and len(separated_secrets) != 3:
            raise RuntimeError("JWT, OAuth state and MFA recovery secrets must be distinct")
        if self.production and not self.auth_cookie_secure:
            raise RuntimeError("AUTH_COOKIE_SECURE must be true in production")
        if self.production and not self.refresh_require_origin:
            raise RuntimeError("REFRESH_REQUIRE_ORIGIN must be true in production")
        if self.auth_rate_limit_backend not in {"memory", "redis"}:
            raise RuntimeError("AUTH_RATE_LIMIT_BACKEND must be memory or redis")
        if self.ai_search_provider not in {"groq", "openai"}:
            raise RuntimeError("AI_SEARCH_PROVIDER must be groq or openai")
        groq_origin = urlsplit(self.groq_base_url)
        if (
            groq_origin.scheme != "https"
            or not groq_origin.hostname
            or groq_origin.username
            or groq_origin.password
            or groq_origin.query
            or groq_origin.fragment
        ):
            raise RuntimeError("GROQ_BASE_URL must be an HTTPS URL without credentials")
        if self.production and self.auth_rate_limit_backend != "redis":
            raise RuntimeError("AUTH_RATE_LIMIT_BACKEND must be redis in production")
        if self.production and not self.redis_enabled:
            raise RuntimeError("REDIS_ENABLED must be true in production")
        if self.production and not self.rate_limit_fail_closed:
            raise RuntimeError("RATE_LIMIT_FAIL_CLOSED must be true in production")
        if self.contact_turnstile_enabled and (
            not self.turnstile_site_key or not self.turnstile_secret_key
        ):
            raise RuntimeError("Turnstile site and secret keys must be configured when enabled")
        if self.mastodon_default_visibility not in {"public", "unlisted", "private", "direct"}:
            raise RuntimeError("MASTODON_DEFAULT_VISIBILITY is invalid")
        if self.mastodon_enabled and not self.mastodon_access_token:
            raise RuntimeError("MASTODON_ACCESS_TOKEN must be configured when Mastodon is enabled")
        if self.mastodon_sso_enabled and not self.mastodon_sso_encryption_key:
            raise RuntimeError(
                "MASTODON_SSO_ENCRYPTION_KEY must be configured when Mastodon SSO is enabled"
            )
        if self.mastodon_sso_enabled and self.mastodon_sso_encryption_key:
            try:
                Fernet(self.mastodon_sso_encryption_key.encode())
            except (TypeError, ValueError) as exc:
                raise RuntimeError("MASTODON_SSO_ENCRYPTION_KEY is invalid") from exc
        if self.mfa_encryption_key:
            try:
                Fernet(self.mfa_encryption_key.encode())
            except (TypeError, ValueError) as exc:
                raise RuntimeError("MFA_ENCRYPTION_KEY is invalid") from exc
        app_origin = urlsplit(self.app_base_url)
        if (
            app_origin.scheme not in {"http", "https"}
            or not app_origin.hostname
            or app_origin.username
            or app_origin.password
            or app_origin.path not in {"", "/"}
            or app_origin.query
            or app_origin.fragment
        ):
            raise RuntimeError("APP_BASE_URL must be an absolute HTTP(S) origin without path")
        if self.production and app_origin.scheme != "https":
            raise RuntimeError("APP_BASE_URL must use HTTPS in production")
        if self.production and not self.webauthn_origin.startswith("https://"):
            raise RuntimeError("WEBAUTHN_ORIGIN must use HTTPS in production")
        if "://" in self.webauthn_rp_id or "/" in self.webauthn_rp_id:
            raise RuntimeError("WEBAUTHN_RP_ID must be a hostname without scheme or path")
        origin = urlsplit(self.webauthn_origin)
        if (
            origin.scheme not in {"http", "https"}
            or not origin.hostname
            or origin.username
            or origin.password
            or origin.path not in {"", "/"}
            or origin.query
            or origin.fragment
        ):
            raise RuntimeError("WEBAUTHN_ORIGIN must be an HTTP(S) origin without path")
        rp_id = self.webauthn_rp_id.lower().rstrip(".")
        origin_host = origin.hostname.lower().rstrip(".")
        if origin_host != rp_id and not origin_host.endswith(f".{rp_id}"):
            raise RuntimeError("WEBAUTHN_RP_ID must match the WebAuthn origin hostname")
        if self.mastodon_area_update_debounce_seconds < 0:
            raise RuntimeError("MASTODON_AREA_UPDATE_DEBOUNCE_SECONDS must not be negative")
        if not 0 <= self.mastodon_boundary_change_min_ratio <= 1:
            raise RuntimeError("MASTODON_BOUNDARY_CHANGE_MIN_RATIO must be between 0 and 1")

    @property
    def mastodon_hashtag_list(self) -> list[str]:
        return [
            value.strip().lstrip("#")
            for value in self.mastodon_hashtags.split(",")
            if value.strip()
        ]

    @property
    def configured_oauth_providers(self) -> list[str]:
        providers: list[str] = []
        if self.github_client_id and self.github_client_secret:
            providers.append("github")
        if self.google_client_id and self.google_client_secret:
            providers.append("google")
        if self.mastodon_sso_enabled and self.mastodon_sso_encryption_key:
            providers.append("mastodon")
        return providers


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_security()
    return settings
