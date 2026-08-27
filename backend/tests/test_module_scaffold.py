import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CREATE_MODULE = ROOT / "scripts/create-module"


def prepare_repository(root: Path) -> None:
    for directory in (
        root / "backend/app/modules",
        root / "backend/tests/modules",
        root / "frontend/frontend-modules",
        root / "frontend/tests",
        root / "frontend/app/pages",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    (root / "backend/app/__init__.py").write_text(
        "from pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n",
        encoding="utf-8",
    )
    (root / "backend/app/modules/__init__.py").write_text("", encoding="utf-8")
    (root / "backend/tests/modules/__init__.py").write_text("", encoding="utf-8")


def run_scaffold(root: Path, module_id: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CREATE_MODULE), module_id, "--root", str(root)],
        check=False,
        capture_output=True,
        text=True,
    )


def generated_files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_valid_module_id_creates_minimal_backend_frontend_and_tests(tmp_path: Path) -> None:
    prepare_repository(tmp_path)

    result = run_scaffold(tmp_path, "hello-world")

    assert result.returncode == 0, result.stderr
    expected = {
        "backend/app/modules/hello_world/__init__.py",
        "backend/app/modules/hello_world/README.md",
        "backend/app/modules/hello_world/settings.py",
        "backend/app/modules/hello_world/module.py",
        "backend/app/modules/hello_world/api/__init__.py",
        "backend/app/modules/hello_world/api/router.py",
        "backend/tests/modules/hello_world/__init__.py",
        "backend/tests/modules/hello_world/test_module.py",
        "frontend/frontend-modules/hello-world/module.json",
        "frontend/frontend-modules/hello-world/layer/nuxt.config.ts",
        "frontend/frontend-modules/hello-world/layer/app/pages/modules/hello-world.vue",
        "frontend/tests/hello-world/module.test.ts",
    }
    assert expected <= generated_files(tmp_path)


@pytest.mark.parametrize(
    "module_id",
    ("Hello-World", "hello_world", "-hello", "hello--world", "hello!", "a" * 64),
)
def test_invalid_module_id_is_rejected_without_output(
    tmp_path: Path,
    module_id: str,
) -> None:
    prepare_repository(tmp_path)
    before = generated_files(tmp_path)

    result = run_scaffold(tmp_path, module_id)

    assert result.returncode == 1
    assert "lowercase kebab-case" in result.stderr
    assert generated_files(tmp_path) == before


def test_existing_target_is_never_overwritten(tmp_path: Path) -> None:
    prepare_repository(tmp_path)
    existing = tmp_path / "backend/app/modules/hello_world"
    existing.mkdir()
    marker = existing / "owned.py"
    marker.write_text("owned = True\n", encoding="utf-8")

    result = run_scaffold(tmp_path, "hello-world")

    assert result.returncode == 1
    assert "Refusing to overwrite" in result.stderr
    assert marker.read_text(encoding="utf-8") == "owned = True\n"
    assert not (tmp_path / "frontend/frontend-modules/hello-world").exists()


def test_generated_ids_are_consistent_and_python_module_imports(tmp_path: Path) -> None:
    prepare_repository(tmp_path)
    assert run_scaffold(tmp_path, "hello-world").returncode == 0

    definition = json.loads(
        (tmp_path / "frontend/frontend-modules/hello-world/module.json").read_text(
            encoding="utf-8"
        )
    )
    assert definition["id"] == definition["backendModuleId"] == "hello-world"
    assert definition["publicContributions"]["ui"][0]["id"].startswith("hello-world.")

    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(tmp_path / "backend"), str(ROOT / "backend"))
    )
    imported = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from app.modules.hello_world.module import DEFINITION, MANIFEST; "
                "assert DEFINITION.declared_id == MANIFEST.id == 'hello-world'"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=environment,
    )
    assert imported.returncode == 0, imported.stderr
    linted = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            str(tmp_path / "backend/app/modules/hello_world"),
            str(tmp_path / "backend/tests/modules/hello_world"),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT / "backend",
    )
    assert linted.returncode == 0, linted.stdout + linted.stderr


def test_generated_frontend_satisfies_real_contract(tmp_path: Path) -> None:
    prepare_repository(tmp_path)
    assert run_scaffold(tmp_path, "hello-world").returncode == 0
    discovery = (ROOT / "frontend/module-host/discovery.ts").as_uri()
    script = f"""
      import {{ resolveFrontendModules }} from {json.dumps(discovery)};
      const modules = resolveFrontendModules({{
        modulesDirectory: {json.dumps(str(tmp_path / 'frontend/frontend-modules'))},
        appPagesDirectory: {json.dumps(str(tmp_path / 'frontend/app/pages'))},
        enabledModules: 'hello-world',
        backendModules: 'hello-world@1.0.0'
      }});
      if (modules.length !== 1 || modules[0].id !== 'hello-world') process.exit(1);
    """

    checked = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT / "frontend",
    )
    assert checked.returncode == 0, checked.stderr


def test_generated_module_passes_existing_architecture_checks_without_host_patches(
    tmp_path: Path,
) -> None:
    prepare_repository(tmp_path)
    protected = {
        path: f"unchanged: {path}\n"
        for path in (
            "backend/app/main.py",
            "backend/app/api/router.py",
            "backend/pyproject.toml",
            "frontend/nuxt.config.ts",
            "frontend/app/components/layout/AppShell.vue",
            "frontend/app/components/map/MapCanvas.vue",
        )
    }
    for relative, contents in protected.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding="utf-8")
    assert run_scaffold(tmp_path, "hello-world").returncode == 0

    architecture = tmp_path / "architecture"
    architecture.mkdir()
    shutil.copy(ROOT / "architecture/module-contract-rules.json", architecture)
    (architecture / "module-boundary-baseline.json").write_text(
        '{"version": 1, "entries": []}\n', encoding="utf-8"
    )
    backend_check = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/check_module_architecture.py"),
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert backend_check.returncode == 0, backend_check.stderr

    frontend_scanner = (ROOT / "frontend/module-host/import-boundaries.ts").as_uri()
    frontend_script = f"""
      import {{ scanFrontendArchitecture }} from {json.dumps(frontend_scanner)};
      const violations = scanFrontendArchitecture({{
        repositoryRoot: {json.dumps(str(tmp_path))},
        frontendRoot: {json.dumps(str(tmp_path / 'frontend'))}
      }});
      if (violations.length) {{ console.error(JSON.stringify(violations)); process.exit(1); }}
    """
    frontend_check = subprocess.run(
        ["node", "--input-type=module", "--eval", frontend_script],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT / "frontend",
    )
    assert frontend_check.returncode == 0, frontend_check.stderr
    for relative, contents in protected.items():
        assert (tmp_path / relative).read_text(encoding="utf-8") == contents
