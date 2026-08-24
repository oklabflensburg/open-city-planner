import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
ANSIBLE = ROOT / "deploy/ansible"
ROLE = ANSIBLE / "roles/stadtplaner_otel"


class OpenTelemetryDeploymentTest(unittest.TestCase):
    def test_production_defaults_are_pinned_and_loopback_only(self) -> None:
        defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text(encoding="utf-8"))

        self.assertTrue(defaults["stadtplaner_otel_required"])
        self.assertTrue(defaults["stadtplaner_manage_otel_collector"])
        self.assertEqual(defaults["stadtplaner_otel_endpoint"], "http://127.0.0.1:4317")
        self.assertEqual(defaults["stadtplaner_otel_protocol"], "grpc")
        self.assertEqual(defaults["stadtplaner_otel_service_name"], "stadtplaner-api")
        self.assertEqual(defaults["stadtplaner_otel_collector_version"], "0.153.0")
        self.assertEqual(defaults["stadtplaner_tempo_version"], "2.10.7")
        self.assertEqual(defaults["stadtplaner_tempo_retention"], "336h")
        for checksum_map in (
            defaults["stadtplaner_otel_collector_checksums"],
            defaults["stadtplaner_tempo_checksums"],
        ):
            self.assertEqual(set(checksum_map), {"x86_64", "aarch64"})
            self.assertTrue(all(len(value) == 64 for value in checksum_map.values()))

    def test_deploy_fails_closed_before_release_activation(self) -> None:
        deploy = yaml.safe_load((ANSIBLE / "playbooks/deploy.yml").read_text(encoding="utf-8"))
        role_names = [entry["role"] for entry in deploy[0]["roles"]]
        otel_index = role_names.index("stadtplaner_otel")
        application_index = role_names.index("stadtplaner")
        tasks = (ROLE / "tasks/main.yml").read_text(encoding="utf-8")

        self.assertLess(otel_index, application_index)
        self.assertIn("Wait for required OTLP gRPC endpoint before release activation", tasks)
        self.assertIn("Require healthy managed OpenTelemetry Collector", tasks)
        self.assertIn("Require ready Tempo backend", tasks)
        self.assertIn("state: started", tasks)
        self.assertNotIn("failed_when: false", tasks)

    def test_trace_services_are_hardened_without_public_listeners(self) -> None:
        collector_config = (ROLE / "templates/collector.yml.j2").read_text(encoding="utf-8")
        tempo_config = (ROLE / "templates/tempo.yml.j2").read_text(encoding="utf-8")
        collector_unit = (ROLE / "templates/stadtplaner-otel-collector.service.j2").read_text(
            encoding="utf-8"
        )
        tempo_unit = (ROLE / "templates/stadtplaner-tempo.service.j2").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("0.0.0.0", collector_config + tempo_config)
        self.assertIn("health_check", collector_config)
        self.assertIn("otlp/tempo", collector_config)
        self.assertIn("backend: local", tempo_config)
        for unit in (collector_unit, tempo_unit):
            self.assertIn("NoNewPrivileges=true", unit)
            self.assertIn("PrivateTmp=true", unit)
            self.assertIn("ProtectSystem=strict", unit)
            self.assertIn("ProtectHome=true", unit)

    def test_api_ordering_is_fail_open_at_runtime(self) -> None:
        unit = (
            ANSIBLE / "roles/stadtplaner/templates/stadtplaner-api.service.j2"
        ).read_text(encoding="utf-8")
        tasks = (ANSIBLE / "roles/stadtplaner/tasks/main.yml").read_text(encoding="utf-8")

        self.assertIn("Wants=network-online.target", unit)
        self.assertIn("stadtplaner-otel-collector.service", unit)
        self.assertNotIn("Requires=stadtplaner-otel-collector.service", unit)
        self.assertIn("Generate sampled production trace", tasks)
        self.assertIn("Prove the release trace reached Tempo", tasks)
        self.assertIn("retries: 20", tasks)


if __name__ == "__main__":
    unittest.main()
