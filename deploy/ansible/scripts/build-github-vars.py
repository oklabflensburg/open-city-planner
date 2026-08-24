#!/usr/bin/env python3
"""Build ephemeral Ansible vars from GitHub environment configuration."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.parse import urlsplit

import yaml


CONFIG_VARIABLES = {
    "stadtplaner_backend_env_content": "STADTPLANER_BACKEND_ENV_CONFIG",
    "stadtplaner_frontend_env_content": "STADTPLANER_FRONTEND_ENV_CONFIG",
    "stadtplaner_osm_env_content": "STADTPLANER_OSM_ENV_CONFIG",
}

SECRET_KEYS = {
    "STADTPLANER_DATABASE_URL": "DATABASE_URL",
    "STADTPLANER_JWT_SECRET_KEY": "JWT_SECRET_KEY",
    "STADTPLANER_OAUTH_STATE_SECRET": "OAUTH_STATE_SECRET",
    "STADTPLANER_MFA_RECOVERY_PEPPER": "MFA_RECOVERY_PEPPER",
    "STADTPLANER_MFA_ENCRYPTION_KEY": "MFA_ENCRYPTION_KEY",
    "STADTPLANER_SMTP_HOST": "SMTP_HOST",
    "STADTPLANER_SMTP_USERNAME": "SMTP_USERNAME",
    "STADTPLANER_SMTP_PASSWORD": "SMTP_PASSWORD",
    "STADTPLANER_SMTP_FROM_EMAIL": "SMTP_FROM_EMAIL",
    "STADTPLANER_CONTACT_TO_EMAIL": "CONTACT_TO_EMAIL",
    "STADTPLANER_CONTACT_TO_NAME": "CONTACT_TO_NAME",
    "STADTPLANER_REDIS_URL": "REDIS_URL",
    "STADTPLANER_TURNSTILE_SECRET_KEY": "TURNSTILE_SECRET_KEY",
    "STADTPLANER_GITHUB_CLIENT_SECRET": "GITHUB_CLIENT_SECRET",
    "STADTPLANER_GOOGLE_CLIENT_SECRET": "GOOGLE_CLIENT_SECRET",
    "STADTPLANER_MASTODON_SSO_ENCRYPTION_KEY": "MASTODON_SSO_ENCRYPTION_KEY",
    "STADTPLANER_OPENAI_API_KEY": "OPENAI_API_KEY",
    "STADTPLANER_GROQ_API_KEY": "GROQ_API_KEY",
    "STADTPLANER_NOMINATIM_BASE_URL": "NOMINATIM_BASE_URL",
    "STADTPLANER_NOMINATIM_EMAIL": "NOMINATIM_EMAIL",
    "STADTPLANER_MASTODON_ACCESS_TOKEN": "MASTODON_ACCESS_TOKEN",
}

ALWAYS_REQUIRED_SECRETS = {
    "STADTPLANER_DATABASE_URL",
    "STADTPLANER_JWT_SECRET_KEY",
    "STADTPLANER_OAUTH_STATE_SECRET",
    "STADTPLANER_MFA_RECOVERY_PEPPER",
    "STADTPLANER_MFA_ENCRYPTION_KEY",
}


def assignments(content: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid dotenv line: {raw_line!r}")
        key, value = line.split("=", 1)
        if key in result:
            raise ValueError(f"Duplicate dotenv key: {key}")
        result[key] = value
    return result


def truthy(value: str | None) -> bool:
    return (value or "").strip().strip('"').lower() in {"1", "true", "yes", "on"}


def quoted(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def require_secret(name: str, required: set[str]) -> None:
    if not os.environ.get(name):
        required.add(name)


def validate_otel(values: dict[str, str]) -> dict[str, object]:
    production = values.get("APP_ENVIRONMENT", "").strip().strip('"').lower() == "production"
    enabled = truthy(values.get("OTEL_ENABLED"))
    endpoint = values.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip().strip('"')
    protocol = values.get("OTEL_EXPORTER_OTLP_PROTOCOL", "").strip().strip('"').lower()
    service_name = values.get("OTEL_SERVICE_NAME", "").strip().strip('"')

    if production and not enabled:
        raise ValueError("Production deployment requires OpenTelemetry tracing")
    if enabled and not endpoint:
        raise ValueError(
            "OpenTelemetry is enabled but OTEL_EXPORTER_OTLP_ENDPOINT is empty"
        )
    if protocol != "grpc":
        raise ValueError("Production OpenTelemetry requires OTLP protocol grpc")
    if enabled:
        try:
            parsed = urlsplit(endpoint)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("OTEL_EXPORTER_OTLP_ENDPOINT is invalid") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or port is None
            or not 1 <= port <= 65535
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "OTEL_EXPORTER_OTLP_ENDPOINT must be an HTTP(S) origin with an explicit "
                "port and without credentials, path, query or fragment"
            )
        if not service_name:
            raise ValueError("OTEL_SERVICE_NAME must not be empty when tracing is enabled")
        return {
            "stadtplaner_otel_enabled": True,
            "stadtplaner_otel_endpoint": endpoint,
            "stadtplaner_otel_endpoint_host": parsed.hostname,
            "stadtplaner_otel_endpoint_port": port,
            "stadtplaner_otel_protocol": protocol,
            "stadtplaner_otel_service_name": service_name,
        }
    return {"stadtplaner_otel_enabled": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--example", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    reference = yaml.safe_load(args.example.read_text(encoding="utf-8"))
    generated: dict[str, str] = {}
    secret_dotenv_keys = set(SECRET_KEYS.values())

    for ansible_key, environment_name in CONFIG_VARIABLES.items():
        content = os.environ.get(environment_name, "").strip()
        if not content:
            raise SystemExit(f"Missing GitHub environment variable: {environment_name}")
        supplied = assignments(content)
        expected = set(assignments(reference[ansible_key]))
        forbidden = sorted(set(supplied) & secret_dotenv_keys)
        if forbidden:
            raise SystemExit(
                f"Secrets must not be present in {environment_name}: {', '.join(forbidden)}"
            )
        expected_public = expected - secret_dotenv_keys if ansible_key == "stadtplaner_backend_env_content" else expected
        missing = sorted(expected_public - set(supplied))
        extra = sorted(set(supplied) - expected_public)
        if missing or extra:
            raise SystemExit(
                f"Invalid {environment_name}; missing={missing or 'none'}, extra={extra or 'none'}"
            )
        generated[ansible_key] = content + "\n"

    backend_values = assignments(generated["stadtplaner_backend_env_content"])
    try:
        generated.update(validate_otel(backend_values))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    avatar_upload_dir = backend_values.get("AVATAR_UPLOAD_DIR", "").strip().strip('"')
    avatar_path = Path(avatar_upload_dir)
    if not avatar_path.is_absolute() or avatar_path == Path("/"):
        raise SystemExit("AVATAR_UPLOAD_DIR must be an absolute non-root path")
    generated["stadtplaner_avatar_upload_dir"] = avatar_upload_dir

    required = set(ALWAYS_REQUIRED_SECRETS)
    if backend_values.get("EMAIL_BACKEND", "").strip('"') == "smtp":
        required.update(
            {
                "STADTPLANER_SMTP_HOST",
                "STADTPLANER_SMTP_USERNAME",
                "STADTPLANER_SMTP_PASSWORD",
                "STADTPLANER_SMTP_FROM_EMAIL",
                "STADTPLANER_CONTACT_TO_EMAIL",
                "STADTPLANER_CONTACT_TO_NAME",
            }
        )
    if truthy(backend_values.get("REDIS_ENABLED")):
        required.add("STADTPLANER_REDIS_URL")
    if truthy(backend_values.get("CONTACT_TURNSTILE_ENABLED")):
        required.add("STADTPLANER_TURNSTILE_SECRET_KEY")
    if backend_values.get("GITHUB_CLIENT_ID", "").strip('"'):
        required.add("STADTPLANER_GITHUB_CLIENT_SECRET")
    if backend_values.get("GOOGLE_CLIENT_ID", "").strip('"'):
        required.add("STADTPLANER_GOOGLE_CLIENT_SECRET")
    if truthy(backend_values.get("MASTODON_SSO_ENABLED")):
        required.add("STADTPLANER_MASTODON_SSO_ENCRYPTION_KEY")
    if truthy(backend_values.get("MASTODON_ENABLED")):
        required.add("STADTPLANER_MASTODON_ACCESS_TOKEN")
    if truthy(backend_values.get("AI_SEARCH_ENABLED")):
        provider = backend_values.get("AI_SEARCH_PROVIDER", "").strip('"').lower()
        required.add("STADTPLANER_OPENAI_API_KEY" if provider == "openai" else "STADTPLANER_GROQ_API_KEY")

    absent = sorted(name for name in required if not os.environ.get(name))
    if absent:
        raise SystemExit(f"Missing required GitHub environment secrets: {', '.join(absent)}")

    secret_lines = [f"{dotenv_key}={quoted(os.environ.get(secret_name, ''))}" for secret_name, dotenv_key in SECRET_KEYS.items()]
    generated["stadtplaner_backend_env_content"] += "\n".join(secret_lines) + "\n"

    args.output.write_text(
        yaml.safe_dump(generated, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    args.output.chmod(0o600)


if __name__ == "__main__":
    main()
