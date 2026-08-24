import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
ANSIBLE = ROOT / "deploy/ansible"
APP_ROLE = ANSIBLE / "roles/stadtplaner"
RUNTIME_ROLE = ANSIBLE / "roles/stadtplaner_map_renderer"


class MapPreviewDeploymentTest(unittest.TestCase):
    def test_renderer_has_a_dedicated_runtime_role(self) -> None:
        playbook = (ANSIBLE / "playbooks/deploy.yml").read_text(encoding="utf-8")
        runtime_tasks = (RUNTIME_ROLE / "tasks/main.yml").read_text(encoding="utf-8")
        runtime_defaults = yaml.safe_load(
            (RUNTIME_ROLE / "defaults/main.yml").read_text(encoding="utf-8")
        )
        self.assertIn("role: stadtplaner_map_renderer", playbook)
        self.assertLess(
            playbook.index("role: stadtplaner_map_renderer"),
            playbook.index("role: stadtplaner\n"),
        )
        self.assertIn("Ubuntu 24.04", runtime_tasks)
        self.assertIn("ansible_architecture", runtime_tasks)
        self.assertIn("https://github.com/maplibre/maplibre-native/releases/download/", runtime_tasks)
        self.assertIn("checksum: \"sha256:", runtime_tasks)
        self.assertIn("create_home: false", runtime_tasks)
        self.assertNotIn("latest", runtime_tasks)
        self.assertEqual(runtime_defaults["stadtplaner_map_renderer_version"], "6.4.1")
        self.assertTrue(
            runtime_defaults["stadtplaner_map_renderer_integrity"].startswith("sha512-")
        )
        self.assertEqual(
            set(runtime_defaults["stadtplaner_map_renderer_archive_checksums"]),
            {"x86_64", "aarch64"},
        )
        self.assertTrue(
            all(
                len(value) == 64
                for value in runtime_defaults[
                    "stadtplaner_map_renderer_archive_checksums"
                ].values()
            )
        )
        self.assertIn(
            "libicu74", runtime_defaults["stadtplaner_map_renderer_runtime_packages"]
        )
        self.assertIn(
            "libgl1-mesa-dri",
            runtime_defaults["stadtplaner_map_renderer_runtime_packages"],
        )
        self.assertIn("xvfb", runtime_defaults["stadtplaner_map_renderer_runtime_packages"])
        self.assertIn("xauth", runtime_defaults["stadtplaner_map_renderer_runtime_packages"])

    def test_renderer_is_loopback_only_dedicated_and_hardened(self) -> None:
        unit = (APP_ROLE / "templates/stadtplaner-map-renderer.service.j2").read_text(
            encoding="utf-8"
        )
        self.assertIn("User={{ stadtplaner_map_renderer_service_user }}", unit)
        self.assertIn(
            "MAP_PREVIEW_HOST={{ stadtplaner_map_renderer_bind_address }}", unit
        )
        self.assertIn("stadtplaner-light.json", unit)
        self.assertIn("STADTPLANER_RELEASE_ROOT", unit)
        self.assertIn("NoNewPrivileges=true", unit)
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("ProtectKernelModules=true", unit)
        self.assertIn("MemoryMax=", unit)
        self.assertIn('/usr/bin/xvfb-run -a -s "-screen 0 1280x720x24 -nolisten tcp"', unit)
        self.assertNotIn("EnvironmentFile=", unit)
        self.assertNotIn("0.0.0.0", unit)

    def test_renderer_participates_in_preflight_rollout_smoke_and_rollback(self) -> None:
        tasks = (APP_ROLE / "tasks/main.yml").read_text(encoding="utf-8")
        self.assertIn("map-preview-renderer/preflight.mjs", tasks)
        self.assertIn("Require all native renderer shared libraries to resolve", tasks)
        self.assertIn("Match the release-installed native binary", tasks)
        self.assertIn("stadtplaner-map-renderer.service.j2", tasks)
        self.assertGreaterEqual(tasks.count("stadtplaner-map-renderer.service"), 4)
        self.assertIn("/health/ready", tasks)
        self.assertIn("/health/smoke.webp", tasks)
        self.assertIn("/health/map-preview.webp", tasks)
        self.assertIn("Verify renderer returned to the previous release", tasks)
        self.assertIn("stadtplaner_map_preview_cache_dir", tasks)

    def test_preview_defaults_are_persistent_and_loopback_only(self) -> None:
        defaults = yaml.safe_load(
            (ANSIBLE / "inventory/group_vars/all.yml").read_text(encoding="utf-8")
        )
        self.assertEqual(
            defaults["stadtplaner_map_renderer_bind_address"], "127.0.0.1"
        )
        self.assertEqual(defaults["stadtplaner_map_renderer_port"], 3020)
        self.assertEqual(defaults["stadtplaner_map_renderer_max_concurrency"], 2)
        self.assertNotEqual(defaults["stadtplaner_map_renderer_service_user"], "root")
        self.assertTrue(defaults["stadtplaner_map_preview_cache_dir"].startswith("/data/"))
        self.assertNotEqual(defaults["stadtplaner_map_preview_cache_dir"], "/")

    def test_nginx_does_not_publish_renderer(self) -> None:
        nginx = (APP_ROLE / "templates/stadtplaner.nginx.conf.j2").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("stadtplaner_map_renderer_port", nginx)
        self.assertNotIn("/internal-render", nginx)
        self.assertNotIn("/renderer/", nginx)


if __name__ == "__main__":
    unittest.main()
