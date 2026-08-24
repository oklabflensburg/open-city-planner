import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
ANSIBLE = ROOT / "deploy/ansible"
ROLE = ANSIBLE / "roles/stadtplaner_monitoring"


class MonitoringDeploymentTest(unittest.TestCase):
    def test_secure_loopback_defaults_and_bounded_retention(self) -> None:
        defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text(encoding="utf-8"))

        self.assertEqual(defaults["monitoring_grafana_bind_address"], "127.0.0.1")
        self.assertEqual(defaults["monitoring_prometheus_bind_address"], "127.0.0.1")
        self.assertEqual(defaults["monitoring_node_exporter_bind_address"], "127.0.0.1")
        self.assertEqual(defaults["monitoring_blackbox_bind_address"], "127.0.0.1")
        self.assertFalse(defaults["monitoring_grafana_publish"])
        self.assertEqual(defaults["monitoring_prometheus_retention_time"], "30d")
        self.assertEqual(defaults["monitoring_prometheus_retention_size"], "10GB")
        self.assertEqual(defaults["monitoring_grafana_admin_password"], "")
        tasks = (ROLE / "tasks/main.yml").read_text(encoding="utf-8")
        self.assertNotIn("0.0.0.0:{{ monitoring_prometheus_port }}", tasks)
        self.assertIn("Wildcard monitoring listeners are", tasks)

    def test_monitoring_assets_are_provisioned_from_canonical_files(self) -> None:
        tasks = (ROLE / "tasks/main.yml").read_text(encoding="utf-8")
        prometheus = (ROLE / "templates/prometheus.yml.j2").read_text(encoding="utf-8")
        datasource = (ROLE / "templates/grafana-datasource.yml.j2").read_text(encoding="utf-8")

        self.assertIn("observability/prometheus/alerts.yml", tasks)
        self.assertIn("observability/grafana/stadtplaner-overview.json", tasks)
        self.assertIn("promtool check config", tasks)
        self.assertIn("promtool check rules", tasks)
        self.assertIn("job_name: stadtplaner-api", prometheus)
        self.assertIn("job_name: stadtplaner-readiness", prometheus)
        self.assertIn("job_name: stadtplaner-node", prometheus)
        self.assertIn("uid: stadtplaner-prometheus", datasource)

    def test_monitoring_is_opt_in_and_documented(self) -> None:
        deploy = yaml.safe_load((ANSIBLE / "playbooks/deploy.yml").read_text(encoding="utf-8"))
        monitoring = yaml.safe_load((ANSIBLE / "playbooks/monitoring.yml").read_text(encoding="utf-8"))
        docs = (ROOT / "docs/monitoring-deployment.md").read_text(encoding="utf-8")

        normal_roles = deploy[0]["roles"]
        self.assertNotIn("stadtplaner_monitoring", str(normal_roles))
        self.assertEqual(monitoring[0]["hosts"], "monitoring")
        self.assertIn("stadtplaner_monitoring", str(monitoring[0]["roles"]))
        self.assertIn("Zugriff ohne Subdomain", docs)
        self.assertIn("Optionale Grafana-Subdomain", docs)
        self.assertIn("Separater Monitoring-Server", docs)


if __name__ == "__main__":
    unittest.main()
