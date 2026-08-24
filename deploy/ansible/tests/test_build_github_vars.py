import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "deploy/ansible/scripts/build-github-vars.py"
EXAMPLE = ROOT / "deploy/ansible/vault.example.yml"
SPEC = importlib.util.spec_from_file_location("build_github_vars", SCRIPT)
assert SPEC and SPEC.loader
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class GitHubVarsBuilderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.reference = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
        secret_keys = set(BUILDER.SECRET_KEYS.values())
        backend = "\n".join(
            line
            for line in self.reference["stadtplaner_backend_env_content"].splitlines()
            if not (
                line.strip()
                and not line.lstrip().startswith("#")
                and line.split("=", 1)[0] in secret_keys
            )
        )
        self.environment = {
            **os.environ,
            "STADTPLANER_BACKEND_ENV_CONFIG": backend,
            "STADTPLANER_FRONTEND_ENV_CONFIG": self.reference[
                "stadtplaner_frontend_env_content"
            ],
            "STADTPLANER_OSM_ENV_CONFIG": self.reference["stadtplaner_osm_env_content"],
        }
        required = BUILDER.ALWAYS_REQUIRED_SECRETS | {
            "STADTPLANER_SMTP_HOST",
            "STADTPLANER_SMTP_USERNAME",
            "STADTPLANER_SMTP_PASSWORD",
            "STADTPLANER_SMTP_FROM_EMAIL",
            "STADTPLANER_CONTACT_TO_EMAIL",
            "STADTPLANER_CONTACT_TO_NAME",
            "STADTPLANER_REDIS_URL",
        }
        self.environment.update({name: "test-value-with-#-and-$" for name in required})

    def run_builder(self, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--example",
                str(EXAMPLE),
                "--output",
                str(output),
            ],
            env=self.environment,
            check=False,
            capture_output=True,
            text=True,
        )

    def set_backend_value(self, key: str, value: str) -> None:
        lines = self.environment["STADTPLANER_BACKEND_ENV_CONFIG"].splitlines()
        self.environment["STADTPLANER_BACKEND_ENV_CONFIG"] = "\n".join(
            f"{key}={value}" if line.startswith(f"{key}=") else line for line in lines
        )

    def test_builds_complete_restricted_ansible_vars(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "vars.yml"
            result = self.run_builder(output)

            self.assertEqual(result.returncode, 0, result.stderr)
            generated = yaml.safe_load(output.read_text(encoding="utf-8"))
            actual = set(BUILDER.assignments(generated["stadtplaner_backend_env_content"]))
            expected = set(
                BUILDER.assignments(self.reference["stadtplaner_backend_env_content"])
            )
            self.assertEqual(actual, expected)
            self.assertEqual(generated["stadtplaner_avatar_upload_dir"], "/data/uploads")
            self.assertTrue(generated["stadtplaner_otel_enabled"])
            self.assertEqual(
                generated["stadtplaner_otel_endpoint"], "http://127.0.0.1:4317"
            )
            self.assertEqual(generated["stadtplaner_otel_endpoint_host"], "127.0.0.1")
            self.assertEqual(generated["stadtplaner_otel_endpoint_port"], 4317)
            self.assertEqual(generated["stadtplaner_otel_protocol"], "grpc")
            self.assertEqual(generated["stadtplaner_otel_service_name"], "stadtplaner-api")
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_rejects_secret_in_open_configuration(self) -> None:
        self.environment["STADTPLANER_BACKEND_ENV_CONFIG"] += "\nDATABASE_URL=exposed"
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_builder(Path(directory) / "vars.yml")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Secrets must not be present", result.stderr)

    def test_rejects_enabled_otel_without_endpoint(self) -> None:
        self.set_backend_value("OTEL_EXPORTER_OTLP_ENDPOINT", "")
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_builder(Path(directory) / "vars.yml")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "OpenTelemetry is enabled but OTEL_EXPORTER_OTLP_ENDPOINT is empty",
            result.stderr,
        )

    def test_rejects_invalid_otel_endpoint(self) -> None:
        self.set_backend_value(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://user:password@127.0.0.1:4317?token=x"
        )
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_builder(Path(directory) / "vars.yml")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("without credentials, path, query or fragment", result.stderr)

    def test_rejects_disabled_otel_for_production(self) -> None:
        self.set_backend_value("OTEL_ENABLED", "false")
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_builder(Path(directory) / "vars.yml")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Production deployment requires OpenTelemetry tracing", result.stderr)

    def test_rejects_non_grpc_protocol(self) -> None:
        self.set_backend_value("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_builder(Path(directory) / "vars.yml")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires OTLP protocol grpc", result.stderr)


if __name__ == "__main__":
    unittest.main()
