from __future__ import annotations

import hashlib
import importlib
import io
import json
import os
import tarfile
import zipfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.cli import module_migrations
from app.platform.modules.discovery import (
    EntryPointModuleDiscovery,
    activate_enabled_module_python_paths,
)
from app.platform.modules.installer import (
    EnablementEnvironment,
    ModuleInstallConflictError,
    ModuleInstaller,
    ModuleLockError,
    ModulePackageError,
    ModulesLock,
    calculate_package_digest,
    installed_backend_distribution_paths,
    read_modules_lock,
    serialize_modules_lock,
    write_modules_lock_atomic,
)
from app.platform.modules.runtime import resolve_module_definitions


def _manifest(
    module_id: str,
    *,
    version: str = "1.0.0",
    host: str = ">=0.2.0,<1.0.0",
    backend: bool = False,
    frontend: bool = True,
    required: dict[str, str] | None = None,
    optional: dict[str, str] | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "manifest_version": 1,
        "id": module_id,
        "name": module_id,
        "version": version,
        "requires": {
            "host": host,
            "sdk": ">=1.7.0,<2.0.0",
            "modules": required or {},
        },
        "optional": {"modules": optional or {}},
        "capabilities": [],
        "permissions": [],
    }
    if backend:
        result["backend"] = {"package": f"ocp-module-{module_id}"}
    if frontend:
        result["frontend"] = {"package": f"@publisher/{module_id}"}
    return result


def _wheel(root: Path, module_id: str, manifest: dict[str, object]) -> Path:
    import_name = f"ocp_module_{module_id.replace('-', '_')}"
    distribution = f"ocp_module_{module_id.replace('-', '_')}"
    version = str(manifest["version"])
    wheel = root / "backend" / f"{distribution}-{version}-py3-none-any.whl"
    wheel.parent.mkdir(parents=True)
    dist_info = f"{distribution}-{version}.dist-info"
    module_source = f'''from app.platform.modules.sdk import ModuleDefinition, parse_manifest

MANIFEST = parse_manifest({manifest!r})

class FixtureModule:
    manifest = MANIFEST

    def __init__(self):
        from .lazy import VALUE
        self.lazy_value = VALUE

    def register(self, context):
        return None

DEFINITION = ModuleDefinition(
    manifest=MANIFEST,
    loader=FixtureModule,
    origin=__name__,
    declared_id=MANIFEST.id,
)
'''
    files = {
        f"{import_name}/__init__.py": "",
        f"{import_name}/lazy.py": "VALUE = 'loaded lazily'\n",
        f"{import_name}/module.py": module_source,
        f"{dist_info}/METADATA": (
            "Metadata-Version: 2.1\n"
            f"Name: ocp-module-{module_id}\n"
            f"Version: {version}\n"
        ),
        f"{dist_info}/WHEEL": (
            "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ),
        f"{dist_info}/entry_points.txt": (
            "[open_city_planner.modules]\n"
            f"{module_id} = {import_name}.module:DEFINITION\n"
        ),
        f"{dist_info}/RECORD": "",
    }
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, contents in files.items():
            archive.writestr(name, contents)
    return wheel


def _frontend_archive(
    root: Path,
    module_id: str,
    version: str,
    *,
    backend: bool,
) -> Path:
    archive_path = root / "frontend" / f"{module_id}-{version}.tgz"
    archive_path.parent.mkdir(parents=True)
    definition = {
        "schemaVersion": 1,
        "id": module_id,
        "version": version,
        "compatibility": {
            "host": ">=1.0.0 <2.0.0",
            "sdk": ">=1.0.0 <2.0.0",
            **({"backend": f">={version} <2.0.0"} if backend else {}),
        },
        **({"backendModuleId": module_id} if backend else {}),
        "layer": "layer",
        "requires": {"modules": {}},
        "publicContributions": {
            "routes": [
                {
                    "path": f"/{module_id}",
                    "source": f"layer/app/pages/{module_id}.vue",
                }
            ],
            "ui": [],
            "map": {"sources": [], "layers": []},
        },
    }
    members = {
        "module.json": json.dumps(definition),
        "layer/nuxt.config.ts": "export default defineNuxtConfig({})\n",
        f"layer/app/pages/{module_id}.vue": "<template><p>fixture</p></template>\n",
    }
    with tarfile.open(archive_path, "w:gz") as archive:
        for name, contents in members.items():
            payload = contents.encode()
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return archive_path


def _package(
    parent: Path,
    module_id: str,
    *,
    version: str = "1.0.0",
    host: str = ">=0.2.0,<1.0.0",
    backend: bool = False,
    frontend: bool = True,
    required: dict[str, str] | None = None,
    optional: dict[str, str] | None = None,
) -> Path:
    root = parent / f"package-{module_id}"
    root.mkdir()
    manifest = _manifest(
        module_id,
        version=version,
        host=host,
        backend=backend,
        frontend=frontend,
        required=required,
        optional=optional,
    )
    backend_path = _wheel(root, module_id, manifest) if backend else None
    frontend_path = (
        _frontend_archive(root, module_id, version, backend=backend) if frontend else None
    )
    backend_payload = (
        None if backend_path is None else (backend_path.name, backend_path.read_bytes())
    )
    frontend_payload = (
        None if frontend_path is None else (frontend_path.name, frontend_path.read_bytes())
    )
    descriptor = {
        "module_id": module_id,
        "version": version,
        "publisher": "fixture-publisher",
        "source": {"type": "local", "reference": f"fixtures/{module_id}"},
        "provenance": {
            "source_repository": "https://github.com/example/module",
            "source_commit": "a" * 40,
            "source_tag": f"v{version}",
            "build_workflow": "github-actions/module-release",
            "license": "AGPL-3.0-only",
            "sbom_reference": None,
            "attestation_reference": None,
        },
        "artifact": {
            "identifier": f"{module_id}-{version}",
            "sha256": calculate_package_digest(backend_payload, frontend_payload),
        },
        "manifest": manifest,
        "backend": (
            None
            if backend_path is None
            else {
                "path": backend_path.relative_to(root).as_posix(),
                "artifact": backend_path.name,
                "sha256": hashlib.sha256(backend_path.read_bytes()).hexdigest(),
            }
        ),
        "frontend": (
            None
            if frontend_path is None
            else {
                "path": frontend_path.relative_to(root).as_posix(),
                "artifact": frontend_path.name,
                "sha256": hashlib.sha256(frontend_path.read_bytes()).hexdigest(),
            }
        ),
    }
    (root / "verified-package-input.json").write_text(json.dumps(descriptor))
    return root


def _installer(
    root: Path,
    *,
    migration_calls: list[tuple[str, ...]] | None = None,
    frontend_calls: list[EnablementEnvironment] | None = None,
) -> ModuleInstaller:
    return ModuleInstaller(
        root,
        host_version="0.2.0",
        migration_preflight=(
            None if migration_calls is None else lambda ids: migration_calls.append(ids)
        ),
        frontend_preflight=(
            None
            if frontend_calls is None
            else lambda environment: frontend_calls.append(environment)
        ),
    )


def _refresh_frontend_digests(package: Path) -> None:
    descriptor_path = package / "verified-package-input.json"
    descriptor = json.loads(descriptor_path.read_text())
    frontend_path = package / descriptor["frontend"]["path"]
    frontend_payload = frontend_path.read_bytes()
    descriptor["frontend"]["sha256"] = hashlib.sha256(frontend_payload).hexdigest()
    backend = descriptor.get("backend")
    backend_payload = (
        None
        if backend is None
        else (
            backend["artifact"],
            (package / backend["path"]).read_bytes(),
        )
    )
    descriptor["artifact"]["sha256"] = calculate_package_digest(
        backend_payload,
        (descriptor["frontend"]["artifact"], frontend_payload),
    )
    descriptor_path.write_text(json.dumps(descriptor))


def _refresh_backend_digests(package: Path) -> None:
    descriptor_path = package / "verified-package-input.json"
    descriptor = json.loads(descriptor_path.read_text())
    backend = descriptor["backend"]
    backend_payload = (package / backend["path"]).read_bytes()
    backend["sha256"] = hashlib.sha256(backend_payload).hexdigest()
    frontend = descriptor.get("frontend")
    frontend_payload = (
        None
        if frontend is None
        else (frontend["artifact"], (package / frontend["path"]).read_bytes())
    )
    descriptor["artifact"]["sha256"] = calculate_package_digest(
        (backend["artifact"], backend_payload),
        frontend_payload,
    )
    descriptor_path.write_text(json.dumps(descriptor))


def test_lockfile_roundtrip_is_deterministic_and_strict(tmp_path: Path) -> None:
    package_a = _package(tmp_path, "alpha")
    package_z = _package(tmp_path, "zeta")
    installer = _installer(tmp_path / "state")
    zeta = installer.install(package_z)
    alpha = installer.install(package_a)

    lock = read_modules_lock(installer.lock_path)
    assert [entry.id for entry in lock.modules] == ["alpha", "zeta"]
    assert serialize_modules_lock(lock).endswith("\n")
    assert serialize_modules_lock(lock) == serialize_modules_lock(
        ModulesLock(modules=(alpha, zeta))
    )

    invalid_version = tmp_path / "future.lock"
    invalid_version.write_text('{"format_version":2,"modules":[]}\n')
    with pytest.raises(ModuleLockError, match="format_version"):
        read_modules_lock(invalid_version)

    with pytest.raises(ValidationError, match="duplicate module IDs"):
        ModulesLock(modules=(alpha, alpha))


@pytest.mark.parametrize(
    "entry_update",
    (
        {"enabled": "false"},
        {"version": "1.0"},
        {"artifact": {"identifier": "alpha-1.0.0", "sha256": "ABC"}},
        {"unexpected": True},
    ),
)
def test_lockfile_rejects_invalid_fields(
    tmp_path: Path,
    entry_update: dict[str, object],
) -> None:
    package = _package(tmp_path, "strict-lock")
    installer = _installer(tmp_path / "state")
    installer.install(package)
    data = json.loads(installer.lock_path.read_text())
    data["modules"][0].update(entry_update)
    installer.lock_path.write_text(json.dumps(data))

    with pytest.raises(ModuleLockError):
        read_modules_lock(installer.lock_path)


def test_install_is_disabled_and_enable_disable_preserve_artifacts(tmp_path: Path) -> None:
    package = _package(tmp_path, "energy-analysis", backend=True, frontend=True)
    migration_calls: list[tuple[str, ...]] = []
    frontend_calls: list[EnablementEnvironment] = []
    installer = _installer(
        tmp_path / "state",
        migration_calls=migration_calls,
        frontend_calls=frontend_calls,
    )

    installed = installer.install(package)
    assert installed.enabled is False
    version_root = installer.root / "installed/energy-analysis/1.0.0"
    assert (version_root / "backend/site-packages").is_dir()
    assert (version_root / "frontend-modules/energy-analysis/module.json").is_file()

    enabled = installer.enable("energy-analysis")
    assert enabled.enabled is True
    assert migration_calls == [("energy-analysis",)]
    assert frontend_calls[0].frontend_modules == "energy-analysis"
    assert "site-packages" in frontend_calls[0].runtime_backend_paths

    disabled = installer.disable("energy-analysis")
    assert disabled.enabled is False
    assert version_root.is_dir()
    assert installer.disable("energy-analysis") == disabled

    installer.enable("energy-analysis")
    assert read_modules_lock(installer.lock_path).modules[0].enabled is True


def test_verify_installable_runs_real_structure_checks_without_state(tmp_path: Path) -> None:
    package = _package(tmp_path, "verify-only", backend=True, frontend=True)
    installer = _installer(tmp_path / "state")

    verified = installer.verify_installable(package)

    assert verified.module_id == "verify-only"
    assert not installer.root.exists()


def test_real_wheel_entry_point_is_discoverable_after_install(tmp_path: Path) -> None:
    package = _package(tmp_path, "wheel-contract", backend=True, frontend=False)
    installer = _installer(tmp_path / "state")
    installer.install(package)
    site_packages = installer.root / "installed/wheel-contract/1.0.0/backend/site-packages"
    previous = os.sys.path.copy()
    definitions = EntryPointModuleDiscovery(
        distribution_paths=(site_packages,)
    ).discover(frozenset({"wheel-contract"}))
    resolved = resolve_module_definitions(
        enabled_module_ids=("wheel-contract",),
        discovery_providers=(
            EntryPointModuleDiscovery(distribution_paths=(site_packages,)),
        ),
        host_version="0.2.0",
    )
    runtime = resolved[0][0].loader()
    assert [definition.declared_id for definition in definitions] == ["wheel-contract"]
    assert [manifest.id for _, manifest in resolved] == ["wheel-contract"]
    assert runtime.lazy_value == "loaded lazily"
    assert os.sys.path == previous


def test_incompatible_package_installs_disabled_but_enable_fails(tmp_path: Path) -> None:
    package = _package(
        tmp_path,
        "future-host",
        host=">=9.0.0,<10.0.0",
        backend=True,
        frontend=False,
    )
    installer = _installer(tmp_path / "state")
    assert installer.install(package).enabled is False

    original = installer.lock_path.read_bytes()
    with pytest.raises(Exception, match="requires host"):
        installer.enable("future-host")
    assert installer.lock_path.read_bytes() == original
    assert read_modules_lock(installer.lock_path).modules[0].enabled is False


def test_required_and_optional_dependencies_reuse_manifest_preflight(tmp_path: Path) -> None:
    required = _package(
        tmp_path,
        "requires-base",
        backend=True,
        frontend=False,
        required={"base-module": ">=1.0.0,<2.0.0"},
    )
    optional = _package(
        tmp_path,
        "optional-base",
        backend=True,
        frontend=False,
        optional={"base-module": ">=1.0.0,<2.0.0"},
    )
    installer = _installer(tmp_path / "state")
    installer.install(required)
    installer.install(optional)

    with pytest.raises(Exception, match="requires module"):
        installer.enable("requires-base")
    assert installer.enable("optional-base").enabled is True


@pytest.mark.parametrize(
    ("field", "value"),
    (("module_id", "different-id"), ("version", "2.0.0")),
)
def test_package_identity_mismatch_fails_without_state(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    package = _package(tmp_path, "mismatch-id" if field == "module_id" else "mismatch-version")
    descriptor_path = package / "verified-package-input.json"
    descriptor = json.loads(descriptor_path.read_text())
    descriptor[field] = value
    descriptor_path.write_text(json.dumps(descriptor))
    installer = _installer(tmp_path / "state")

    with pytest.raises(ModulePackageError, match="does not match"):
        installer.install(package)
    assert not installer.lock_path.exists()
    assert not (installer.root / "installed").exists()


def test_digest_mismatch_is_atomic(tmp_path: Path) -> None:
    first = _package(tmp_path, "existing")
    broken = _package(tmp_path, "broken-digest")
    installer = _installer(tmp_path / "state")
    installer.install(first)
    original = installer.lock_path.read_bytes()
    descriptor_path = broken / "verified-package-input.json"
    descriptor = json.loads(descriptor_path.read_text())
    descriptor["frontend"]["sha256"] = "0" * 64
    descriptor_path.write_text(json.dumps(descriptor))

    with pytest.raises(ModulePackageError, match="SHA-256 mismatch"):
        installer.install(broken)
    assert installer.lock_path.read_bytes() == original
    assert not (installer.root / "installed/broken-digest").exists()


@pytest.mark.parametrize("unsafe", ("../../etc/passwd", "/tmp/module.tgz"))
def test_unsafe_artifact_paths_are_rejected(tmp_path: Path, unsafe: str) -> None:
    package = _package(tmp_path, "unsafe-path")
    descriptor_path = package / "verified-package-input.json"
    descriptor = json.loads(descriptor_path.read_text())
    descriptor["frontend"]["path"] = unsafe
    descriptor_path.write_text(json.dumps(descriptor))

    with pytest.raises(ModulePackageError, match="relative POSIX paths"):
        _installer(tmp_path / "state").install(package)


def test_symlink_escape_and_artifact_collision_are_rejected(tmp_path: Path) -> None:
    package = _package(tmp_path, "symlink-escape")
    descriptor_path = package / "verified-package-input.json"
    descriptor = json.loads(descriptor_path.read_text())
    outside = tmp_path / "outside.tgz"
    outside.write_bytes(b"outside")
    artifact = package / descriptor["frontend"]["path"]
    artifact.unlink()
    artifact.symlink_to(outside)
    with pytest.raises(ModulePackageError, match="symbolic links"):
        _installer(tmp_path / "state-a").install(package)

    valid = _package(tmp_path, "collision")
    installer = _installer(tmp_path / "state-b")
    first = installer.install(valid)
    assert installer.install(valid) == first
    descriptor_path = valid / "verified-package-input.json"
    descriptor = json.loads(descriptor_path.read_text())
    descriptor["publisher"] = "changed-publisher"
    descriptor_path.write_text(json.dumps(descriptor))
    with pytest.raises(ModuleInstallConflictError, match="already installed"):
        installer.install(valid)


@pytest.mark.parametrize("unsafe_member", ("duplicate", "symlink"))
def test_frontend_archive_collisions_and_links_are_rejected(
    tmp_path: Path,
    unsafe_member: str,
) -> None:
    package = _package(tmp_path, f"unsafe-archive-{unsafe_member}")
    descriptor = json.loads((package / "verified-package-input.json").read_text())
    archive_path = package / descriptor["frontend"]["path"]
    with tarfile.open(archive_path, "w:gz") as archive:
        if unsafe_member == "duplicate":
            for payload in (b"first", b"second"):
                info = tarfile.TarInfo("module.json")
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
        else:
            info = tarfile.TarInfo("module.json")
            info.type = tarfile.SYMTYPE
            info.linkname = "../../outside"
            archive.addfile(info)
    _refresh_frontend_digests(package)

    expected = "Duplicate frontend archive path" if unsafe_member == "duplicate" else "may not contain links"
    with pytest.raises(ModulePackageError, match=expected):
        _installer(tmp_path / "state").install(package)


def test_builtin_collision_and_inventory_kinds(tmp_path: Path) -> None:
    installer = ModuleInstaller(
        tmp_path / "state",
        host_version="0.2.0",
        builtin_enabled_ids=("reference",),
        builtin_frontend_enabled_ids=("reference",),
    )
    with pytest.raises(ModuleInstallConflictError, match="built-in"):
        installer.install(_package(tmp_path, "reference"))

    installer.install(_package(tmp_path, "inventory-installed"))
    inventory = installer.inventory()
    by_id = {entry.id: entry for entry in inventory.modules}
    assert by_id["reference"].kind == "built-in"
    assert by_id["reference"].enabled is True
    assert by_id["inventory-installed"].kind == "installed"
    assert by_id["inventory-installed"].enabled is False


def test_excluded_builtin_allows_external_install_enable_disable_reenable(
    tmp_path: Path,
) -> None:
    installer = ModuleInstaller(
        tmp_path / "state",
        host_version="0.2.0",
        builtin_enabled_ids=("reference",),
        builtin_frontend_enabled_ids=("reference",),
        excluded_builtin_module_ids=("reference",),
    )

    installed = installer.install(_package(tmp_path, "reference", backend=True))
    assert installed.enabled is False
    disabled_environment = installer.enablement_environment()
    assert disabled_environment.enabled_modules == ""
    assert disabled_environment.frontend_modules == ""
    assert disabled_environment.runtime_backend_paths == ""
    assert disabled_environment.excluded_builtin_modules == "reference"
    inventory = installer.inventory().modules
    assert [(entry.id, entry.kind) for entry in inventory if entry.id == "reference"] == [
        ("reference", "installed")
    ]

    assert installer.enable("reference").enabled is True
    assert installer.enablement_environment().enabled_modules == "reference"
    assert "site-packages" in installer.enablement_environment().runtime_backend_paths
    assert installer.disable("reference").enabled is False
    assert installer.enablement_environment().runtime_backend_paths == ""
    assert installer.enable("reference").enabled is True


def test_disable_never_runs_preflight_or_removes_migration_resources(tmp_path: Path) -> None:
    package = _package(tmp_path, "migration-history", backend=True, frontend=False)
    calls: list[tuple[str, ...]] = []
    installer = _installer(tmp_path / "state", migration_calls=calls)
    installer.install(package)
    installer.enable("migration-history")
    calls.clear()
    installer.disable("migration-history")

    assert calls == []
    environment = installer.enablement_environment()
    assert environment.enabled_modules == ""
    assert environment.runtime_backend_paths == ""
    assert "migration-history/1.0.0/backend/site-packages" in (
        str(installed_backend_distribution_paths(installer.root)[0])
    )


def test_runtime_paths_include_only_enabled_modules_and_follow_disable(
    tmp_path: Path,
) -> None:
    installer = _installer(tmp_path / "state")
    installer.install(_package(tmp_path, "enabled-package", backend=True, frontend=False))
    installer.install(_package(tmp_path, "disabled-package", backend=True, frontend=False))
    installer.enable("enabled-package")

    environment = installer.enablement_environment()
    assert "enabled-package" in environment.runtime_backend_paths
    assert "disabled-package" not in environment.runtime_backend_paths
    assert {path.parents[2].name for path in installed_backend_distribution_paths(installer.root)} == {
        "disabled-package",
        "enabled-package",
    }

    previous = os.sys.path.copy()
    runtime_paths = tuple(
        Path(value)
        for value in environment.runtime_backend_paths.split(os.pathsep)
        if value
    )
    activate_enabled_module_python_paths(runtime_paths)
    try:
        assert str(runtime_paths[0]) == os.sys.path[-1]
        assert "disabled-package" not in os.pathsep.join(os.sys.path)
    finally:
        os.sys.path[:] = previous

    installer.disable("enabled-package")
    assert installer.enablement_environment().runtime_backend_paths == ""
    installer.enable("enabled-package")
    assert "enabled-package" in installer.enablement_environment().runtime_backend_paths


def test_backend_wheel_rejects_host_shadowing_namespace(tmp_path: Path) -> None:
    package = _package(tmp_path, "shadow-test", backend=True, frontend=False)
    descriptor = json.loads((package / "verified-package-input.json").read_text())
    wheel = package / descriptor["backend"]["path"]
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr("host_shadow_fixture/__init__.py", "SOURCE = 'module'\n")
    _refresh_backend_digests(package)

    with pytest.raises(ModulePackageError, match="forbidden top-level namespace"):
        _installer(tmp_path / "state").install(package)


def test_disabled_installed_path_cannot_shadow_host_import(tmp_path: Path) -> None:
    installer = _installer(tmp_path / "state")
    installer.install(_package(tmp_path, "shadow-test", backend=True, frontend=False))
    installed_path = installed_backend_distribution_paths(installer.root)[0]
    shadow = installed_path / "host_shadow_fixture"
    shadow.mkdir()
    (shadow / "__init__.py").write_text("SOURCE = 'disabled-module'\n")
    host_path = tmp_path / "host"
    host_package = host_path / "host_shadow_fixture"
    host_package.mkdir(parents=True)
    (host_package / "__init__.py").write_text("SOURCE = 'host'\n")
    previous = os.sys.path.copy()
    os.sys.path.insert(0, str(host_path))
    os.sys.modules.pop("host_shadow_fixture", None)
    try:
        activate_enabled_module_python_paths(())
        imported = importlib.import_module("host_shadow_fixture")
        assert imported.SOURCE == "host"
        assert str(installed_path) not in os.sys.path
    finally:
        os.sys.modules.pop("host_shadow_fixture", None)
        os.sys.path[:] = previous


def test_migration_run_scopes_all_installed_paths_independent_of_enablement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installer = _installer(tmp_path / "state")
    installer.install(_package(tmp_path, "enabled-history", backend=True, frontend=False))
    installer.install(_package(tmp_path, "disabled-history", backend=True, frontend=False))
    installer.enable("enabled-history")
    all_paths = installed_backend_distribution_paths(installer.root)
    all_path_values = set(map(str, all_paths))
    observed: list[tuple[str, ...]] = []

    class RecordingCoordinator:
        def preflight(self):
            observed.append(tuple(value for value in os.sys.path if value in all_path_values))
            return ()

    monkeypatch.setattr(
        module_migrations,
        "coordinator",
        lambda **kwargs: RecordingCoordinator(),
    )
    before = os.sys.path.copy()

    module_migrations.run(
        "preflight",
        install_root=installer.root,
        enabled_module_ids=("enabled-history",),
    )

    assert set(observed[0]) == all_path_values
    assert os.sys.path == before


def test_failed_atomic_lock_write_keeps_previous_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock_path = tmp_path / "modules.lock"
    write_modules_lock_atomic(lock_path, ModulesLock())
    original = lock_path.read_bytes()

    def fail_replace(source: Path, target: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        write_modules_lock_atomic(lock_path, ModulesLock())
    assert lock_path.read_bytes() == original
