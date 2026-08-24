import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
ANSIBLE = ROOT / "deploy/ansible"
ROLE = ANSIBLE / "roles/stadtplaner_otel"


class OpenTelemetryDeploymentTest(unittest.TestCase):
    @staticmethod
    def _role_tasks() -> list[dict]:
        return yaml.safe_load((ROLE / "tasks/main.yml").read_text(encoding="utf-8"))

    @classmethod
    def _task(cls, name: str) -> dict:
        return next(task for task in cls._role_tasks() if task.get("name") == name)

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

    def test_configs_use_isolated_non_world_readable_paths(self) -> None:
        defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text(encoding="utf-8"))
        collector = self._task("Install OpenTelemetry Collector configuration")
        tempo = self._task("Install Grafana Tempo configuration")

        self.assertEqual(
            defaults["stadtplaner_otel_collector_config"],
            "{{ stadtplaner_otel_collector_config_dir }}/collector.yml",
        )
        self.assertEqual(
            defaults["stadtplaner_tempo_config"],
            "{{ stadtplaner_tempo_config_dir }}/tempo.yml",
        )
        self.assertEqual(collector["ansible.builtin.template"]["group"], "stadtplaner-otel")
        self.assertEqual(collector["ansible.builtin.template"]["mode"], "0640")
        self.assertEqual(tempo["ansible.builtin.template"]["group"], "stadtplaner-tempo")
        self.assertEqual(tempo["ansible.builtin.template"]["mode"], "0640")

    def test_restricted_parent_uses_idempotent_traverse_only_acls(self) -> None:
        tasks = self._role_tasks()
        task_names = [task.get("name") for task in tasks]
        serialized = (ROLE / "tasks/main.yml").read_text(encoding="utf-8")

        self.assertIn(
            "Install POSIX ACL support for restricted configuration traversal", task_names
        )
        self.assertIn("Read application configuration directory ACLs", task_names)
        self.assertIn("Read managed observability configuration root ACLs", task_names)
        self.assertIn("user:{{ item }}:--x", serialized)
        self.assertIn("not in stadtplaner_otel_parent_acl.stdout_lines", serialized)
        self.assertIn("not in stadtplaner_otel_config_root_acl.stdout_lines", serialized)
        parent = self._task("Preserve the restricted application configuration directory")
        directories = self._task("Create managed OpenTelemetry directories")["loop"]
        config_directories = [item for item in directories if "config" in item["path"]]
        self.assertEqual(parent["ansible.builtin.file"]["mode"], "0750")
        self.assertTrue(config_directories)
        self.assertTrue(all(item["mode"] == "0750" for item in config_directories))

    def test_permission_and_validation_preflights_run_before_service_start(self) -> None:
        tasks = self._role_tasks()
        task_names = [task.get("name") for task in tasks]
        enable_index = task_names.index("Enable managed trace services")

        for name, service_user in (
            (
                "OpenTelemetry Collector service user can read collector configuration",
                "stadtplaner-otel",
            ),
            ("Grafana Tempo service user can read Tempo configuration", "stadtplaner-tempo"),
        ):
            task = self._task(name)
            self.assertLess(task_names.index(name), enable_index)
            self.assertEqual(task["become_user"], service_user)
            self.assertIn("-r", task["ansible.builtin.command"]["argv"])

        collector_validation = self._task("Validate OpenTelemetry Collector configuration")
        tempo_validation = self._task("Validate Grafana Tempo configuration")
        self.assertLess(task_names.index(collector_validation["name"]), enable_index)
        self.assertLess(task_names.index(tempo_validation["name"]), enable_index)
        self.assertIn("validate", collector_validation["ansible.builtin.command"]["argv"])
        self.assertIn(
            "-config.verify=true", tempo_validation["ansible.builtin.command"]["argv"]
        )

    def test_tempo_startup_503_is_retried_and_all_listeners_are_checked(self) -> None:
        readiness = self._task("Require ready Tempo backend before release activation")
        tempo_otlp = self._task(
            "Wait for managed Tempo OTLP gRPC endpoint before release activation"
        )
        collector_otlp = self._task(
            "Wait for required OTLP gRPC endpoint before release activation"
        )
        collector_health = self._task(
            "Require healthy managed OpenTelemetry Collector before release activation"
        )

        self.assertEqual(readiness["ansible.builtin.uri"]["status_code"], [200, 503])
        self.assertEqual(readiness["retries"], 30)
        self.assertEqual(readiness["delay"], 2)
        self.assertIn("status == 200", readiness["until"])
        self.assertEqual(
            tempo_otlp["ansible.builtin.wait_for"]["port"],
            "{{ stadtplaner_tempo_otlp_grpc_port }}",
        )
        self.assertEqual(
            collector_otlp["ansible.builtin.wait_for"]["port"],
            "{{ stadtplaner_otel_endpoint_port }}",
        )
        self.assertIn(
            "stadtplaner_otel_collector_health_port",
            collector_health["ansible.builtin.uri"]["url"],
        )

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
            self.assertIn("UMask=0027", unit)

        self.assertIn("stadtplaner_otel_collector_config", collector_unit)
        self.assertIn("stadtplaner_tempo_config", tempo_unit)

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
