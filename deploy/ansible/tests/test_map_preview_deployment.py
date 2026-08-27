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

    def test_renderer_has_writable_cache_under_systemd_hardening(self) -> None:
        unit = (APP_ROLE / "templates/stadtplaner-map-renderer.service.j2").read_text(
            encoding="utf-8"
        )
        self.assertIn("CacheDirectory=stadtplaner-map-renderer", unit)
        self.assertIn("CacheDirectoryMode=0750", unit)
        self.assertIn(
            "Environment=XDG_CACHE_HOME=/var/cache/stadtplaner-map-renderer",
            unit,
        )
        self.assertIn(
            "Environment=MESA_SHADER_CACHE_DIR=/var/cache/stadtplaner-map-renderer/mesa-shader-cache",
            unit,
        )
        self.assertIn("ProtectSystem=strict", unit)
        self.assertNotIn("Environment=XDG_CACHE_HOME=/nonexistent", unit)
        self.assertNotIn("Environment=MESA_SHADER_CACHE_DIR=/nonexistent", unit)

    def test_renderer_participates_in_preflight_rollout_smoke_and_rollback(self) -> None:
        tasks = (APP_ROLE / "tasks/main.yml").read_text(encoding="utf-8")
        binary_smoke = (APP_ROLE / "tasks/webp_smoke.yml").read_text(encoding="utf-8")
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
        self.assertEqual(tasks.count("include_tasks: webp_smoke.yml"), 2)
        self.assertIn("ansible.builtin.get_url", binary_smoke)
        self.assertIn("always:", binary_smoke)
        self.assertNotIn("return_content", binary_smoke)
        self.assertNotIn("MODULE_STRICT_UTF8_RESPONSE", tasks + binary_smoke)

    def test_first_renderer_deployment_rollback_restores_old_environment(self) -> None:
        tasks = (APP_ROLE / "tasks/main.yml").read_text(encoding="utf-8")
        api_unit = (APP_ROLE / "templates/stadtplaner-api.service.j2").read_text(
            encoding="utf-8"
        )
        frontend_unit = (
            APP_ROLE / "templates/stadtplaner-frontend.service.j2"
        ).read_text(encoding="utf-8")
        self.assertIn("Snapshot legacy active environments for rollback", tasks)
        self.assertIn("Restore the previous backend environment link", tasks)
        self.assertIn("Restore the previous frontend environment link", tasks)
        self.assertLess(
            tasks.index("Restore the previous backend environment link"),
            tasks.index("Start previous API and frontend releases"),
        )
        self.assertIn("Stop renderer when rolling back across its first deployment", tasks)
        self.assertIn("Wait for API port after rollback", tasks)
        self.assertLess(
            tasks.index("Wait for API port after rollback"),
            tasks.index("Verify API readiness after rollback"),
        )
        self.assertNotIn("Environment=MAP_PREVIEW_", api_unit)
        self.assertNotIn("Environment=STADTPLANER_RELEASE_SHA", api_unit)
        self.assertNotIn("Environment=STADTPLANER_RELEASE_SHA", frontend_unit)

    def test_target_environment_is_validated_before_activation(self) -> None:
        tasks = (APP_ROLE / "tasks/main.yml").read_text(encoding="utf-8")
        self.assertIn("Validate target backend settings before release activation", tasks)
        self.assertIn("Validate target frontend environment syntax", tasks)
        self.assertIn("Resolve target release backend module inventory", tasks)
        self.assertIn("Bind generated backend module inventory", tasks)
        self.assertIn("Verify target frontend module compatibility", tasks)
        self.assertLess(
            tasks.index("Validate target backend settings before release activation"),
            tasks.index("Resolve target release backend module inventory"),
        )
        self.assertLess(
            tasks.index("Resolve target release backend module inventory"),
            tasks.index("Bind generated backend module inventory"),
        )
        self.assertLess(
            tasks.index("Bind generated backend module inventory"),
            tasks.index("Verify target frontend module compatibility"),
        )
        self.assertLess(
            tasks.index("Validate target backend settings before release activation"),
            tasks.index("Activate the target backend environment snapshot"),
        )
        self.assertIn("Preserve the original deployment failure", tasks)
        self.assertIn("Report both deployment and rollback failures", tasks)
        self.assertGreaterEqual(tasks.count("STADTPLANER_RELEASE_SHA="), 4)

    def test_target_environment_release_sha_is_written_as_a_real_line(self) -> None:
        tasks_path = APP_ROLE / "tasks/main.yml"
        tasks_text = tasks_path.read_text(encoding="utf-8")
        tasks = yaml.safe_load(tasks_text)
        tasks_by_name = {task["name"]: task for task in tasks}

        for name in (
            "Install target backend environment snapshot from encrypted input",
            "Install target frontend environment snapshot from encrypted input",
        ):
            content = tasks_by_name[name]["ansible.builtin.copy"]["content"]
            self.assertNotIn("stadtplaner_release_sha", content)
            self.assertNotIn("~", content)

        bind_task = tasks_by_name[
            "Bind target environment snapshots to the target release SHA"
        ]
        lineinfile = bind_task["ansible.builtin.lineinfile"]
        self.assertEqual(lineinfile["regexp"], "^STADTPLANER_RELEASE_SHA=")
        self.assertEqual(
            lineinfile["line"],
            "STADTPLANER_RELEASE_SHA={{ stadtplaner_release_sha }}",
        )
        self.assertEqual(lineinfile["insertafter"], "EOF")
        self.assertFalse(lineinfile["create"])
        self.assertEqual(
            bind_task["loop"],
            [
                "{{ stadtplaner_target_backend_env }}",
                "{{ stadtplaner_target_frontend_env }}",
            ],
        )
        self.assertNotIn("when", bind_task)
        self.assertNotIn("~ '\\nSTADTPLANER_RELEASE_SHA='", tasks_text)

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
