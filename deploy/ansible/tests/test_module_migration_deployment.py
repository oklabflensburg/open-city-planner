import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
TASKS_PATH = ROOT / "deploy/ansible/roles/stadtplaner/tasks/main.yml"


class ModuleMigrationDeploymentTest(unittest.TestCase):
    def test_backup_preflight_and_upgrade_order_is_fail_closed(self) -> None:
        tasks = yaml.safe_load(TASKS_PATH.read_text(encoding="utf-8"))
        by_name = {task["name"]: task for task in tasks}
        names = [task["name"] for task in tasks]
        managed_backup = "Require published managed database backup before migration"
        custom_backup = "Create custom pre-migration database backup"
        preflight = "Preflight Host and module migrations"
        upgrade = "Apply Host and module migrations"

        self.assertLess(names.index(managed_backup), names.index(preflight))
        self.assertLess(names.index(custom_backup), names.index(preflight))
        self.assertLess(names.index(preflight), names.index(upgrade))

        expected_environment = {
            "OCP_MODULE_INSTALL_ROOT": "{{ stadtplaner_module_install_root }}"
        }
        self.assertEqual(by_name[preflight]["environment"], expected_environment)
        self.assertEqual(by_name[upgrade]["environment"], expected_environment)
        self.assertEqual(
            by_name[preflight]["ansible.builtin.command"]["cmd"],
            ".venv/bin/python -m app.cli.module_migrations preflight",
        )
        self.assertEqual(
            by_name[upgrade]["ansible.builtin.command"]["cmd"],
            ".venv/bin/python -m app.cli.module_migrations upgrade",
        )

        role_source = TASKS_PATH.read_text(encoding="utf-8")
        self.assertNotIn(".venv/bin/alembic upgrade head", role_source)


if __name__ == "__main__":
    unittest.main()
