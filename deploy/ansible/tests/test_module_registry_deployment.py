import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
ANSIBLE = ROOT / "deploy/ansible"


class ModuleRegistryDeploymentTest(unittest.TestCase):
    def test_registry_install_is_opt_in_exact_and_runs_before_environment(self) -> None:
        defaults = yaml.safe_load(
            (ANSIBLE / "inventory/group_vars/all.yml").read_text(encoding="utf-8")
        )
        tasks = yaml.safe_load(
            (ANSIBLE / "roles/stadtplaner/tasks/main.yml").read_text(encoding="utf-8")
        )
        by_name = {task["name"]: task for task in tasks}
        install_name = "Install exact Registry module releases for the target deployment"
        render_name = "Render installed module enablement for the target release"
        names = [task["name"] for task in tasks]

        self.assertEqual(defaults["stadtplaner_registry_modules"], [])
        self.assertEqual(
            defaults["stadtplaner_module_registry_url"],
            "https://packages.stadtplaner.oklabflensburg.de",
        )
        self.assertLess(names.index(install_name), names.index(render_name))
        arguments = by_name[install_name]["ansible.builtin.command"]["argv"]
        self.assertIn("install-registry", arguments)
        self.assertIn("--version", arguments)
        self.assertIn("--expected-sha256", arguments)
        self.assertIn("--registry-url", arguments)
        self.assertNotIn("enable", arguments)


if __name__ == "__main__":
    unittest.main()
