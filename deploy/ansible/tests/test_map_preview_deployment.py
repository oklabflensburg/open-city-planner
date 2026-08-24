import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
ANSIBLE = ROOT / "deploy/ansible"
ROLE = ANSIBLE / "roles/stadtplaner"


class MapPreviewDeploymentTest(unittest.TestCase):
    def test_renderer_is_loopback_only_and_hardened(self) -> None:
        unit = (ROLE / "templates/stadtplaner-map-preview.service.j2").read_text(
            encoding="utf-8"
        )
        self.assertIn("MAP_PREVIEW_HOST=127.0.0.1", unit)
        self.assertIn("stadtplaner_map_preview_port", unit)
        self.assertIn("stadtplaner-light.json", unit)
        self.assertIn("NoNewPrivileges=true", unit)
        self.assertIn("ProtectSystem=strict", unit)
        self.assertNotIn("0.0.0.0", unit)

    def test_renderer_participates_in_rollout_and_rollback(self) -> None:
        tasks = (ROLE / "tasks/main.yml").read_text(encoding="utf-8")
        self.assertIn("stadtplaner-map-preview.service.j2", tasks)
        self.assertGreaterEqual(tasks.count("stadtplaner-map-preview.service"), 4)
        self.assertIn("Verify native map preview renderer", tasks)
        self.assertIn("/health", tasks)
        self.assertIn("stadtplaner_map_preview_cache_dir", tasks)

    def test_preview_defaults_are_persistent_and_loopback_only(self) -> None:
        defaults = yaml.safe_load(
            (ANSIBLE / "inventory/group_vars/all.yml").read_text(encoding="utf-8")
        )
        self.assertEqual(defaults["stadtplaner_map_preview_port"], 3020)
        self.assertEqual(defaults["stadtplaner_map_preview_max_concurrent"], 2)
        self.assertTrue(defaults["stadtplaner_map_preview_cache_dir"].startswith("/data/"))


if __name__ == "__main__":
    unittest.main()
