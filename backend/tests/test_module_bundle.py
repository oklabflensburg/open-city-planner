from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from pathlib import Path

import pytest
import yaml

from app.cli import modules as modules_cli
from app.platform.modules.bundle import (
    BUNDLE_CHECKSUMS_PATH,
    BUNDLE_METADATA_PATH,
    MAX_BUNDLE_FILE_SIZE,
    ModuleBundleFormatError,
    ModuleBundleIntegrityError,
    build_ocp_bundle,
    bundle_sha256,
    read_ocp_bundle,
    staged_ocp_bundle,
)
from app.platform.modules.installer import (
    ModuleProvenance,
    ModuleSource,
    installed_backend_distribution_paths,
    read_modules_lock,
)
from tests.test_module_installer import (
    _frontend_archive,
    _installer,
    _manifest,
    _wheel,
)


def _source(module_id: str) -> ModuleSource:
    return ModuleSource(type="local", reference=f"releases/{module_id}")


def _provenance(version: str = "1.0.0") -> ModuleProvenance:
    return ModuleProvenance(
        source_repository="https://github.com/example/ocp-module",
        source_commit="a" * 40,
        source_tag=f"v{version}",
        build_workflow="github-actions/module-release",
        license="AGPL-3.0-only",
    )


def _bundle(
    root: Path,
    module_id: str,
    *,
    backend: bool = True,
    frontend: bool = True,
    output_name: str | None = None,
) -> tuple[Path, dict[str, object]]:
    manifest = _manifest(
        module_id,
        backend=backend,
        frontend=frontend,
    )
    artifacts = root / f"artifacts-{module_id}"
    backend_path = _wheel(artifacts, module_id, manifest) if backend else None
    frontend_path = (
        _frontend_archive(artifacts, module_id, "1.0.0", backend=backend)
        if frontend
        else None
    )
    output = root / (output_name or f"{module_id}-1.0.0.ocp")
    build_ocp_bundle(
        output,
        manifest=manifest,
        publisher="fixture-publisher",
        source=_source(module_id),
        provenance=_provenance(),
        backend_artifact=backend_path,
        frontend_artifact=frontend_path,
    )
    return output, manifest


def _members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {
            info.filename: archive.read(info)
            for info in archive.infolist()
            if not info.is_dir()
        }


def _write_zip(path: Path, members: list[tuple[zipfile.ZipInfo | str, bytes]]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for member, payload in members:
            archive.writestr(member, payload)


def _replace_members(path: Path, members: dict[str, bytes]) -> None:
    _write_zip(path, list(members.items()))


def test_fullstack_bundle_maps_to_existing_installer_and_lifecycle(tmp_path: Path) -> None:
    bundle, _manifest_data = _bundle(tmp_path, "bundle-fullstack")
    installer = _installer(tmp_path / "state")

    with staged_ocp_bundle(bundle) as (package_root, package):
        assert package.module_id == "bundle-fullstack"
        assert package.bundle_sha256 == hashlib.sha256(bundle.read_bytes()).hexdigest()
        verified = installer.verify_installable(package_root)
        assert verified.bundle_sha256 == package.bundle_sha256
        assert not installer.lock_path.exists()

    with staged_ocp_bundle(bundle) as (package_root, _package):
        installed = installer.install(package_root)
    assert installed.enabled is False
    assert installed.artifact.sha256 == bundle_sha256(bundle)
    assert read_modules_lock(installer.lock_path).modules == (installed,)

    assert installer.enable("bundle-fullstack").enabled is True
    assert "bundle-fullstack" in installer.enablement_environment().runtime_backend_paths
    assert installer.disable("bundle-fullstack").enabled is False
    assert installer.enablement_environment().runtime_backend_paths == ""
    assert "bundle-fullstack/1.0.0/backend/site-packages" in str(
        installed_backend_distribution_paths(installer.root)[0]
    )
    assert (installer.root / "installed/bundle-fullstack/1.0.0").is_dir()
    assert installer.enable("bundle-fullstack").enabled is True


@pytest.mark.parametrize(
    ("module_id", "backend", "frontend"),
    (
        ("backend-bundle", True, False),
        ("frontend-bundle", False, True),
    ),
)
def test_backend_only_and_frontend_only_bundles_install(
    tmp_path: Path,
    module_id: str,
    backend: bool,
    frontend: bool,
) -> None:
    bundle, _manifest_data = _bundle(
        tmp_path,
        module_id,
        backend=backend,
        frontend=frontend,
    )
    installer = _installer(tmp_path / f"state-{module_id}")

    with staged_ocp_bundle(bundle) as (package_root, _package):
        entry = installer.install(package_root)

    assert entry.backend.present is backend
    assert entry.frontend.present is frontend
    assert entry.enabled is False
    assert installer.enable(module_id).enabled is True


def test_bundle_build_is_deterministic(tmp_path: Path) -> None:
    first, manifest = _bundle(tmp_path, "deterministic", output_name="first.ocp")
    artifacts = tmp_path / "artifacts-deterministic"
    second = tmp_path / "second.ocp"

    build_ocp_bundle(
        second,
        manifest=manifest,
        publisher="fixture-publisher",
        source=_source("deterministic"),
        provenance=_provenance(),
        backend_artifact=next((artifacts / "backend").glob("*.whl")),
        frontend_artifact=next((artifacts / "frontend").glob("*.tgz")),
    )

    assert first.read_bytes() == second.read_bytes()
    assert bundle_sha256(first) == bundle_sha256(second)


@pytest.mark.parametrize("field", ("module_id", "version"))
def test_bundle_identity_mismatch_fails_before_install(
    tmp_path: Path,
    field: str,
) -> None:
    bundle, _manifest_data = _bundle(tmp_path, f"mismatch-{field.replace('_', '-')}")
    members = _members(bundle)
    metadata = yaml.safe_load(members[BUNDLE_METADATA_PATH])
    metadata[field] = "different-id" if field == "module_id" else "2.0.0"
    members[BUNDLE_METADATA_PATH] = yaml.safe_dump(metadata, sort_keys=False).encode()
    _replace_members(bundle, members)

    with pytest.raises(ModuleBundleFormatError, match="does not match"):
        read_ocp_bundle(bundle, tmp_path / "staging")
    assert not (tmp_path / "state/modules.lock").exists()


def test_unknown_bundle_version_and_unknown_metadata_key_fail(tmp_path: Path) -> None:
    bundle, _manifest_data = _bundle(tmp_path, "strict-metadata")
    original_members = _members(bundle)
    for key, value, expected in (
        ("bundle_format_version", 99, "bundle_format_version"),
        ("trusted", True, "trusted"),
    ):
        members = dict(original_members)
        metadata = yaml.safe_load(members[BUNDLE_METADATA_PATH])
        metadata[key] = value
        members[BUNDLE_METADATA_PATH] = yaml.safe_dump(metadata, sort_keys=False).encode()
        _replace_members(bundle, members)
        with pytest.raises(ModuleBundleFormatError, match=expected):
            read_ocp_bundle(bundle, tmp_path / f"staging-{key}")


@pytest.mark.parametrize("missing", (BUNDLE_METADATA_PATH, BUNDLE_CHECKSUMS_PATH))
def test_required_bundle_members_are_enforced(tmp_path: Path, missing: str) -> None:
    bundle, _manifest_data = _bundle(tmp_path, f"missing-{missing.split('.')[0]}")
    members = _members(bundle)
    members.pop(missing)
    _replace_members(bundle, members)

    with pytest.raises(ModuleBundleFormatError, match="module.yaml|checksums.json|valid ZIP"):
        read_ocp_bundle(bundle, tmp_path / "staging")


def test_payload_checksum_mismatch_is_atomic(tmp_path: Path) -> None:
    bundle, _manifest_data = _bundle(tmp_path, "checksum-mismatch")
    installer = _installer(tmp_path / "state")
    members = _members(bundle)
    payload_path = next(name for name in members if name.startswith("backend/"))
    members[payload_path] += b"modified"
    _replace_members(bundle, members)

    with (
        pytest.raises(ModuleBundleIntegrityError, match="SHA-256 mismatch"),
        staged_ocp_bundle(bundle) as (package_root, _package),
    ):
        installer.install(package_root)
    assert not installer.lock_path.exists()
    assert not installer.root.exists()


@pytest.mark.parametrize("change", ("missing", "unknown"))
def test_checksum_coverage_must_exactly_match_payloads(
    tmp_path: Path,
    change: str,
) -> None:
    bundle, _manifest_data = _bundle(tmp_path, f"checksum-{change}")
    members = _members(bundle)
    checksums = json.loads(members[BUNDLE_CHECKSUMS_PATH])
    if change == "missing":
        checksums["files"].pop(next(iter(checksums["files"])))
    else:
        checksums["files"]["frontend/unknown.tgz"] = "0" * 64
    members[BUNDLE_CHECKSUMS_PATH] = json.dumps(checksums).encode()
    _replace_members(bundle, members)

    with pytest.raises(ModuleBundleIntegrityError, match="exactly the declared"):
        read_ocp_bundle(bundle, tmp_path / "staging")


@pytest.mark.parametrize(
    "name",
    (
        "evil.txt",
        "scripts/install.sh",
        "../escape.whl",
        "/absolute.whl",
        "backend\\escape.whl",
    ),
)
def test_unknown_and_unsafe_bundle_paths_are_rejected(tmp_path: Path, name: str) -> None:
    bundle, _manifest_data = _bundle(tmp_path, "unsafe-roots")
    members = list(_members(bundle).items())
    members.append((name, b"unsafe"))
    _write_zip(bundle, members)

    with pytest.raises(ModuleBundleFormatError, match="path|root|payload"):
        read_ocp_bundle(bundle, tmp_path / "staging")


def test_duplicate_bundle_paths_are_rejected(tmp_path: Path) -> None:
    bundle, _manifest_data = _bundle(tmp_path, "duplicate-path")
    members = list(_members(bundle).items())
    members.append((BUNDLE_METADATA_PATH, b"duplicate"))
    _write_zip(bundle, members)

    with pytest.raises(ModuleBundleFormatError, match="Duplicate OCP bundle path"):
        read_ocp_bundle(bundle, tmp_path / "staging")


@pytest.mark.parametrize("file_type", (stat.S_IFLNK, stat.S_IFIFO))
def test_links_and_special_files_are_rejected(tmp_path: Path, file_type: int) -> None:
    bundle, _manifest_data = _bundle(tmp_path, "special-file")
    members: list[tuple[zipfile.ZipInfo | str, bytes]] = list(_members(bundle).items())
    special = zipfile.ZipInfo("backend/special.whl")
    special.create_system = 3
    special.external_attr = (file_type | 0o777) << 16
    members.append((special, b"target"))
    _write_zip(bundle, members)

    with pytest.raises(ModuleBundleFormatError, match="regular files"):
        read_ocp_bundle(bundle, tmp_path / "staging")


def test_archive_size_limit_is_checked_before_reading_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle, _manifest_data = _bundle(tmp_path, "size-limit")
    monkeypatch.setattr(
        "app.platform.modules.bundle.MAX_BUNDLE_FILE_SIZE",
        16,
    )

    with pytest.raises(ModuleBundleFormatError, match="file size limit"):
        read_ocp_bundle(bundle, tmp_path / "staging")
    assert MAX_BUNDLE_FILE_SIZE > 16


def test_extreme_compression_ratio_is_rejected(tmp_path: Path) -> None:
    bundle = tmp_path / "compression-bomb.ocp"
    _write_zip(bundle, [(BUNDLE_METADATA_PATH, b"x" * (1024 * 1024 + 1))])

    with pytest.raises(ModuleBundleFormatError, match="compression ratio limit"):
        read_ocp_bundle(bundle, tmp_path / "staging")


def test_cli_verify_and_install_accept_ocp_without_second_installer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, _manifest_data = _bundle(
        tmp_path,
        "cli-bundle",
        backend=True,
        frontend=False,
    )
    installer = _installer(tmp_path / "state")
    monkeypatch.setattr(modules_cli, "_installer", lambda _root: installer)

    assert modules_cli.main(["verify", str(bundle)]) == 0
    verify_output = capsys.readouterr().out
    assert '"module_id":"cli-bundle"' in verify_output
    assert not installer.lock_path.exists()

    assert modules_cli.main(["install", str(bundle)]) == 0
    install_output = capsys.readouterr().out
    assert '"enabled":false' in install_output
    assert read_modules_lock(installer.lock_path).modules[0].id == "cli-bundle"


def test_bundle_reader_cleanup_removes_private_staging(tmp_path: Path) -> None:
    bundle, _manifest_data = _bundle(tmp_path, "cleanup")
    with staged_ocp_bundle(bundle) as (package_root, _package):
        assert package_root.is_dir()
        staged_path = package_root
    assert not staged_path.exists()
