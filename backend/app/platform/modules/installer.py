"""Host-owned installation state for verified, locally supplied module packages."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from app.platform.modules.discovery import (
    EntryPointModuleDiscovery,
    FirstPartyModuleDiscovery,
)
from app.platform.modules.manifest import (
    MODULE_ID_PATTERN,
    ModuleManifestV1,
    SemanticVersion,
    parse_manifest,
)
from app.platform.modules.runtime import MODULE_SDK_VERSION, resolve_module_definitions
from app.platform.modules.settings import (
    ModuleSettingsRegistry,
    build_module_settings_registry,
)

LOCK_FORMAT_VERSION = 1
LOCAL_PACKAGE_INPUT_FILENAME = "verified-package-input.json"
DEFAULT_INSTALL_ROOT = Path("/var/lib/stadtplaner/modules")
SHA256_PATTERN = r"^[0-9a-f]{64}$"

ModuleId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=False,
        min_length=1,
        max_length=63,
        pattern=MODULE_ID_PATTERN,
    ),
]
Digest = Annotated[
    str,
    StringConstraints(strip_whitespace=False, pattern=SHA256_PATTERN),
]


class ModuleInstallerError(RuntimeError):
    """Base error for a failed installer operation."""


class ModuleLockError(ModuleInstallerError):
    """The host-owned lock state is missing or invalid."""


class ModulePackageError(ModuleInstallerError):
    """The local package input is unsafe or inconsistent."""


class ModuleInstallConflictError(ModuleInstallerError):
    """The requested package collides with an existing installation."""


class ModuleEnableError(ModuleInstallerError):
    """An installed module cannot be enabled."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ModuleSource(_StrictModel):
    type: Literal["local"]
    reference: str = Field(min_length=1, max_length=512)

    @field_validator("reference")
    @classmethod
    def reference_must_be_portable(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            "\x00" in value
            or "\\" in value
            or path.is_absolute()
            or ".." in path.parts
            or value != path.as_posix()
        ):
            raise ValueError("source references must be portable and non-absolute")
        return value


class LockedArtifact(_StrictModel):
    identifier: str = Field(min_length=1, max_length=255)
    sha256: Digest

    @field_validator("identifier")
    @classmethod
    def identifier_is_not_a_path(cls, value: str) -> str:
        if value in {".", ".."} or "/" in value or "\\" in value or "\x00" in value:
            raise ValueError("artifact identifiers must be plain file names")
        return value


class ModuleProvenance(_StrictModel):
    source_repository: str = Field(min_length=1, max_length=512)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
    source_tag: str | None = Field(default=None, min_length=1, max_length=255)
    build_workflow: str = Field(min_length=1, max_length=512)
    license: str = Field(min_length=1, max_length=255)
    sbom_reference: str | None = Field(default=None, min_length=1, max_length=512)
    attestation_reference: str | None = Field(default=None, min_length=1, max_length=512)

    @field_validator("source_repository")
    @classmethod
    def repository_is_public_metadata(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("source_repository must be an HTTPS URL without credentials")
        return value


class LockedComponent(_StrictModel):
    present: bool
    artifact: str | None = Field(default=None, min_length=1, max_length=255)
    sha256: Digest | None = None

    @model_validator(mode="after")
    def metadata_matches_presence(self) -> LockedComponent:
        if self.present != (self.artifact is not None and self.sha256 is not None):
            raise ValueError("present components require artifact and sha256 together")
        if self.artifact is not None:
            LockedArtifact(identifier=self.artifact, sha256=self.sha256 or "")
        return self


class ModuleLockEntry(_StrictModel):
    id: ModuleId
    version: SemanticVersion
    enabled: bool
    publisher: str = Field(min_length=1, max_length=255)
    source: ModuleSource
    provenance: ModuleProvenance
    artifact: LockedArtifact
    backend: LockedComponent
    frontend: LockedComponent

    @model_validator(mode="after")
    def at_least_one_component_is_present(self) -> ModuleLockEntry:
        if not self.backend.present and not self.frontend.present:
            raise ValueError("a module release requires a backend or frontend artifact")
        return self


class ModulesLock(_StrictModel):
    format_version: Literal[LOCK_FORMAT_VERSION] = LOCK_FORMAT_VERSION
    modules: tuple[ModuleLockEntry, ...] = ()

    @model_validator(mode="after")
    def entries_are_unique_and_sorted(self) -> ModulesLock:
        ids = [entry.id for entry in self.modules]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate module IDs are forbidden in modules.lock")
        if ids != sorted(ids):
            raise ValueError("modules.lock entries must be sorted by canonical module ID")
        return self


class PackageComponentInput(_StrictModel):
    path: str = Field(min_length=1, max_length=512)
    artifact: str = Field(min_length=1, max_length=255)
    sha256: Digest

    @field_validator("path")
    @classmethod
    def path_is_safe_relative(cls, value: str) -> str:
        _validate_relative_path(value)
        return value

    @field_validator("artifact")
    @classmethod
    def artifact_is_plain_name(cls, value: str) -> str:
        LockedArtifact(identifier=value, sha256="0" * 64)
        return value


class VerifiedModulePackage(_StrictModel):
    """Narrow internal handoff from a future bundle reader to the installer."""

    module_id: ModuleId
    version: SemanticVersion
    publisher: str = Field(min_length=1, max_length=255)
    source: ModuleSource
    provenance: ModuleProvenance
    artifact: LockedArtifact
    bundle_sha256: Digest | None = None
    manifest: dict[str, object]
    backend: PackageComponentInput | None = None
    frontend: PackageComponentInput | None = None

    @model_validator(mode="after")
    def has_payload(self) -> VerifiedModulePackage:
        if self.backend is None and self.frontend is None:
            raise ValueError("a package input requires a backend or frontend artifact")
        return self


class InstalledModuleInventoryEntry(_StrictModel):
    id: ModuleId
    version: SemanticVersion
    kind: Literal["built-in", "installed"]
    enabled: bool
    publisher: str | None = None
    source: ModuleSource | None = None
    digest: Digest | None = None
    backend_present: bool
    frontend_present: bool


class InstalledModuleInventory(_StrictModel):
    modules: tuple[InstalledModuleInventoryEntry, ...]


class EnablementEnvironment(_StrictModel):
    enabled_modules: str
    frontend_modules: str
    runtime_backend_paths: str
    installed_frontend_module_roots: str
    excluded_builtin_modules: str = ""


def read_modules_lock(path: Path) -> ModulesLock:
    if not path.exists():
        return ModulesLock()
    try:
        return ModulesLock.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ModuleLockError(f"Invalid modules.lock at {path}: {exc}") from exc


def serialize_modules_lock(lock: ModulesLock) -> str:
    canonical = ModulesLock(modules=tuple(sorted(lock.modules, key=lambda entry: entry.id)))
    return json.dumps(
        canonical.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def write_modules_lock_atomic(path: Path, lock: ModulesLock) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = serialize_modules_lock(lock)
    descriptor, temporary_name = tempfile.mkstemp("", ".modules.lock.", path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def calculate_package_digest(
    backend: tuple[str, bytes] | None,
    frontend: tuple[str, bytes] | None,
) -> str:
    digest = hashlib.sha256(b"open-city-planner-verified-package-v1\0")
    for component_name, component in (("backend", backend), ("frontend", frontend)):
        if component is None:
            continue
        identifier, payload = component
        digest.update(component_name.encode("ascii") + b"\0")
        digest.update(identifier.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(payload).digest())
    return digest.hexdigest()


class ModuleInstaller:
    """Serialize package installation and lock-state transitions for one host."""

    def __init__(
        self,
        root: Path,
        *,
        host_version: str,
        builtin_enabled_ids: Sequence[str] = (),
        builtin_frontend_enabled_ids: Sequence[str] = (),
        excluded_builtin_module_ids: Sequence[str] = (),
        module_environment: Mapping[str, str] | None = None,
        migration_preflight: Callable[[tuple[str, ...]], None] | None = None,
        frontend_preflight: Callable[[EnablementEnvironment], None] | None = None,
        frontend_package_preflight: Callable[[Path], None] | None = None,
        uv_executable: str = "uv",
    ) -> None:
        self.root = root.resolve()
        self.lock_path = self.root / "modules.lock"
        self.host_version = host_version
        self.excluded_builtin_module_ids = tuple(sorted(set(excluded_builtin_module_ids)))
        # Validate IDs and unknown exclusions once at the composition boundary.
        FirstPartyModuleDiscovery(
            excluded_module_ids=self.excluded_builtin_module_ids
        )
        self.builtin_enabled_ids = tuple(
            sorted(set(builtin_enabled_ids).difference(self.excluded_builtin_module_ids))
        )
        self.builtin_frontend_enabled_ids = tuple(
            sorted(
                set(builtin_frontend_enabled_ids).difference(
                    self.excluded_builtin_module_ids
                )
            )
        )
        self.module_environment = dict(module_environment or {})
        self.migration_preflight = migration_preflight
        self.frontend_preflight = frontend_preflight
        self.frontend_package_preflight = frontend_package_preflight
        self.uv_executable = uv_executable

    def verify(self, package_directory: Path) -> VerifiedModulePackage:
        package_root = package_directory.resolve()
        descriptor_path = package_root / LOCAL_PACKAGE_INPUT_FILENAME
        if not package_root.is_dir() or descriptor_path.is_symlink() or not descriptor_path.is_file():
            raise ModulePackageError(
                f"Local package input must contain {LOCAL_PACKAGE_INPUT_FILENAME}."
            )
        try:
            package = VerifiedModulePackage.model_validate_json(
                descriptor_path.read_text(encoding="utf-8")
            )
            manifest = parse_manifest(package.manifest, origin=str(descriptor_path))
        except (OSError, ValidationError, ValueError) as exc:
            raise ModulePackageError(f"Invalid local package metadata: {exc}") from exc
        if manifest.id != package.module_id:
            raise ModulePackageError("Package metadata module_id does not match manifest ID.")
        if manifest.version != package.version:
            raise ModulePackageError("Package metadata version does not match manifest version.")

        backend = self._read_component(package_root, package.backend)
        frontend = self._read_component(package_root, package.frontend)
        actual_release_digest = calculate_package_digest(
            None if backend is None else (backend[0].artifact, backend[1]),
            None if frontend is None else (frontend[0].artifact, frontend[1]),
        )
        if actual_release_digest != package.artifact.sha256:
            raise ModulePackageError("Module package aggregate SHA-256 does not match.")
        if package.backend is not None and manifest.backend is None:
            raise ModulePackageError("Backend artifact is present but the manifest has no backend package.")
        if package.backend is None and manifest.backend is not None:
            raise ModulePackageError("Manifest declares a backend package but no backend artifact is present.")
        if package.frontend is not None and manifest.frontend is None:
            raise ModulePackageError("Frontend artifact is present but the manifest has no frontend package.")
        if package.frontend is None and manifest.frontend is not None:
            raise ModulePackageError("Manifest declares a frontend package but no frontend artifact is present.")
        return package

    def install(self, package_directory: Path) -> ModuleLockEntry:
        package_root = package_directory.resolve()
        package = self.verify(package_root)
        self._reject_builtin_collision(package.module_id)
        staging_parent = self.root / ".staging"
        staging_parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp("", f"{package.module_id}-", staging_parent))
        final = self._version_root(package.module_id, package.version)
        installed_final = False
        try:
            self._prepare_staging(package_root, package, staging)

            entry = _lock_entry(package, enabled=False)
            with self._transaction_lock():
                current = read_modules_lock(self.lock_path)
                existing = next((item for item in current.modules if item.id == package.module_id), None)
                if existing is not None:
                    if (
                        existing.model_copy(update={"enabled": False}) == entry
                        and final.is_dir()
                    ):
                        return existing
                    raise ModuleInstallConflictError(
                        f'Module "{package.module_id}" is already installed; explicit upgrade is not part of #173.'
                    )
                if final.exists():
                    raise ModuleInstallConflictError(
                        f"Installation target already exists without matching lock state: {final}."
                    )
                final.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staging, final)
                installed_final = True
                try:
                    write_modules_lock_atomic(
                        self.lock_path,
                        ModulesLock(modules=tuple(sorted((*current.modules, entry), key=lambda item: item.id))),
                    )
                except Exception:
                    shutil.rmtree(final, ignore_errors=True)
                    installed_final = False
                    raise
            return entry
        finally:
            if not installed_final:
                shutil.rmtree(staging, ignore_errors=True)

    def verify_installable(self, package_directory: Path) -> VerifiedModulePackage:
        package_root = package_directory.resolve()
        package = self.verify(package_root)
        self._reject_builtin_collision(package.module_id)
        with tempfile.TemporaryDirectory(prefix=f"ocp-verify-{package.module_id}-") as temporary:
            self._prepare_staging(package_root, package, Path(temporary))
        return package

    def enable(self, module_id: str) -> ModuleLockEntry:
        with self._transaction_lock():
            lock = read_modules_lock(self.lock_path)
            entry = self._required_entry(lock, module_id)
            self._verify_installed_entry(entry)
            candidate = entry.model_copy(update={"enabled": True})
            candidate_lock = _replace_entry(lock, candidate)
            self._preflight(candidate_lock)
            write_modules_lock_atomic(self.lock_path, candidate_lock)
            return candidate

    def disable(self, module_id: str) -> ModuleLockEntry:
        with self._transaction_lock():
            lock = read_modules_lock(self.lock_path)
            entry = self._required_entry(lock, module_id)
            if not entry.enabled:
                return entry
            disabled = entry.model_copy(update={"enabled": False})
            write_modules_lock_atomic(self.lock_path, _replace_entry(lock, disabled))
            return disabled

    def inventory(self) -> InstalledModuleInventory:
        lock = read_modules_lock(self.lock_path)
        builtins = FirstPartyModuleDiscovery(
            excluded_module_ids=self.excluded_builtin_module_ids
        ).discover_available()
        installed_ids = {entry.id for entry in lock.modules}
        duplicate = sorted(installed_ids.intersection(definition.declared_id for definition in builtins))
        if duplicate:
            raise ModuleInstallConflictError(
                f'Duplicate built-in and installed module ID "{duplicate[0]}".'
            )
        builtin_entries = tuple(
            InstalledModuleInventoryEntry(
                id=definition.declared_id,
                version=(
                    definition.manifest.version
                    if isinstance(definition.manifest, ModuleManifestV1)
                    else parse_manifest(definition.manifest).version
                ),
                kind="built-in",
                enabled=definition.declared_id in self.builtin_enabled_ids,
                backend_present=True,
                frontend_present=(
                    Path(__file__).resolve().parents[4]
                    / "frontend/frontend-modules"
                    / definition.declared_id
                    / "module.json"
                ).is_file(),
            )
            for definition in builtins
        )
        installed_entries = tuple(
            InstalledModuleInventoryEntry(
                id=entry.id,
                version=entry.version,
                kind="installed",
                enabled=entry.enabled,
                publisher=entry.publisher,
                source=entry.source,
                digest=entry.artifact.sha256,
                backend_present=entry.backend.present,
                frontend_present=entry.frontend.present,
            )
            for entry in lock.modules
        )
        return InstalledModuleInventory(
            modules=tuple(sorted((*builtin_entries, *installed_entries), key=lambda item: item.id))
        )

    def enablement_environment(self, lock: ModulesLock | None = None) -> EnablementEnvironment:
        active_lock = lock or read_modules_lock(self.lock_path)
        backend_ids = set(self.builtin_enabled_ids)
        frontend_ids = set(self.builtin_frontend_enabled_ids)
        runtime_backend_paths: list[str] = []
        frontend_roots: list[str] = []
        for entry in active_lock.modules:
            version_root = self._version_root(entry.id, entry.version)
            if entry.backend.present and entry.enabled:
                runtime_backend_paths.append(
                    str(version_root / "backend/site-packages")
                )
                backend_ids.add(entry.id)
            if entry.frontend.present:
                frontend_roots.append(str(version_root / "frontend-modules"))
                if entry.enabled:
                    frontend_ids.add(entry.id)
        return EnablementEnvironment(
            enabled_modules=",".join(sorted(backend_ids)),
            frontend_modules=",".join(sorted(frontend_ids)),
            runtime_backend_paths=os.pathsep.join(sorted(runtime_backend_paths)),
            installed_frontend_module_roots=os.pathsep.join(sorted(frontend_roots)),
            excluded_builtin_modules=",".join(self.excluded_builtin_module_ids),
        )

    def _preflight(self, lock: ModulesLock) -> None:
        environment = self.enablement_environment(lock)
        runtime_paths = tuple(
            Path(path)
            for path in environment.runtime_backend_paths.split(os.pathsep)
            if path
        )
        resolved = resolve_module_definitions(
            enabled_module_ids=tuple(filter(None, environment.enabled_modules.split(","))),
            discovery_providers=(
                FirstPartyModuleDiscovery(
                    excluded_module_ids=self.excluded_builtin_module_ids
                ),
                EntryPointModuleDiscovery(distribution_paths=runtime_paths),
            ),
            host_version=self.host_version,
            sdk_version=MODULE_SDK_VERSION,
        )
        build_module_settings_registry(
            resolved,
            registry=ModuleSettingsRegistry(self.module_environment),
        )
        if self.migration_preflight is not None:
            self.migration_preflight(
                tuple(filter(None, environment.enabled_modules.split(",")))
            )
        if self.frontend_preflight is not None:
            self.frontend_preflight(environment)

    def _verify_installed_entry(self, entry: ModuleLockEntry) -> None:
        self._reject_builtin_collision(entry.id)
        version_root = self._version_root(entry.id, entry.version)
        if not version_root.is_dir():
            raise ModuleEnableError(f'Installed artifacts for module "{entry.id}" are missing.')
        for component_name, component in (("backend", entry.backend), ("frontend", entry.frontend)):
            if not component.present:
                continue
            artifact = version_root / "artifacts" / (component.artifact or "")
            if artifact.is_symlink() or not artifact.is_file():
                raise ModuleEnableError(f'{component_name.title()} artifact for module "{entry.id}" is missing.')
            if _sha256_file(artifact) != component.sha256:
                raise ModuleEnableError(f'{component_name.title()} artifact SHA-256 for module "{entry.id}" changed.')

    def _read_component(
        self,
        package_root: Path,
        component: PackageComponentInput | None,
    ) -> tuple[PackageComponentInput, bytes] | None:
        if component is None:
            return None
        path = _safe_input_file(package_root, component.path)
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != component.sha256:
            raise ModulePackageError(f'Artifact SHA-256 mismatch for "{component.artifact}".')
        if path.name != component.artifact:
            raise ModulePackageError("Artifact identifier must match the local artifact file name.")
        return component, payload

    def _prepare_staging(
        self,
        package_root: Path,
        package: VerifiedModulePackage,
        staging: Path,
    ) -> None:
        artifacts = staging / "artifacts"
        artifacts.mkdir(parents=True)
        if package.backend is not None:
            source = _safe_input_file(package_root, package.backend.path)
            wheel = artifacts / package.backend.artifact
            shutil.copyfile(source, wheel)
            site_packages = staging / "backend" / "site-packages"
            self._install_wheel(
                wheel,
                site_packages,
                module_id=package.module_id,
                version=package.version,
            )
            self._verify_backend_definition(site_packages, package)
        if package.frontend is not None:
            source = _safe_input_file(package_root, package.frontend.path)
            archive = artifacts / package.frontend.artifact
            shutil.copyfile(source, archive)
            module_root = staging / "frontend-modules" / package.module_id
            self._extract_frontend_archive(archive, module_root)
            self._verify_frontend_definition(module_root, package)
            if self.frontend_package_preflight is not None:
                self.frontend_package_preflight(staging / "frontend-modules")

    def _install_wheel(
        self,
        wheel: Path,
        site_packages: Path,
        *,
        module_id: str,
        version: str,
    ) -> None:
        self._validate_wheel_namespace(
            wheel,
            module_id=module_id,
            version=version,
        )
        site_packages.mkdir(parents=True)
        command = [
            self.uv_executable,
            "pip",
            "install",
            "--target",
            str(site_packages),
            "--no-index",
            "--no-deps",
            str(wheel),
        ]
        try:
            subprocess.run(command, check=True, text=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            detail = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) else str(exc)
            raise ModulePackageError(f"The verified backend wheel could not be installed: {detail}") from exc

    def _validate_wheel_namespace(
        self,
        wheel: Path,
        *,
        module_id: str,
        version: str,
    ) -> None:
        expected_package = f"ocp_module_{module_id.replace('-', '_')}"
        expected_dist_info = f"{expected_package}-{version}.dist-info"
        top_level: set[str] = set()
        dist_info: set[str] = set()
        seen: set[str] = set()
        try:
            with zipfile.ZipFile(wheel) as archive:
                for member in archive.infolist():
                    raw_name = member.filename.rstrip("/")
                    if not raw_name:
                        continue
                    try:
                        normalized = _validate_relative_path(raw_name).as_posix()
                    except ValueError as exc:
                        raise ModulePackageError(
                            f'Unsafe backend wheel path "{member.filename}".'
                        ) from exc
                    if normalized in seen:
                        raise ModulePackageError(
                            f'Duplicate backend wheel path "{normalized}".'
                        )
                    seen.add(normalized)
                    mode = member.external_attr >> 16
                    if stat.S_ISLNK(mode):
                        raise ModulePackageError("Backend wheels may not contain symbolic links.")
                    root = normalized.partition("/")[0]
                    top_level.add(root)
                    if root.endswith(".dist-info"):
                        dist_info.add(root)
        except (OSError, zipfile.BadZipFile) as exc:
            raise ModulePackageError(f"The backend artifact is not a valid wheel: {exc}") from exc

        allowed = {expected_package, expected_dist_info}
        unexpected = sorted(top_level.difference(allowed))
        if unexpected:
            raise ModulePackageError(
                "Backend wheel contains a forbidden top-level namespace: "
                f'"{unexpected[0]}"; expected only "{expected_package}" and dist-info.'
            )
        if (
            expected_package not in top_level
            or dist_info != {expected_dist_info}
        ):
            raise ModulePackageError(
                "Backend wheel must contain exactly its canonical module package and dist-info directory."
            )

    def _verify_backend_definition(
        self,
        site_packages: Path,
        package: VerifiedModulePackage,
    ) -> None:
        try:
            definitions = EntryPointModuleDiscovery(
                distribution_paths=(site_packages,)
            ).discover(frozenset({package.module_id}))
        finally:
            _purge_modules_from_path(site_packages)
        if len(definitions) != 1:
            raise ModulePackageError(
                f'Backend wheel must expose exactly one "{package.module_id}" entry point.'
            )
        manifest = definitions[0].manifest
        if not isinstance(manifest, ModuleManifestV1):
            manifest = parse_manifest(manifest, origin=definitions[0].origin)
        if manifest.model_dump(mode="json", by_alias=True) != parse_manifest(
            package.manifest
        ).model_dump(mode="json", by_alias=True):
            raise ModulePackageError("Backend wheel manifest does not match package metadata.")

    def _extract_frontend_archive(self, archive: Path, module_root: Path) -> None:
        module_root.mkdir(parents=True)
        seen: set[str] = set()
        try:
            with tarfile.open(archive, "r:*") as source:
                for member in source.getmembers():
                    relative = _validate_relative_path(member.name)
                    normalized = relative.as_posix()
                    if normalized in seen:
                        raise ModulePackageError(f'Duplicate frontend archive path "{normalized}".')
                    seen.add(normalized)
                    if member.issym() or member.islnk():
                        raise ModulePackageError("Frontend archives may not contain links.")
                    target = module_root.joinpath(*relative.parts)
                    if member.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                    elif member.isfile():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        extracted = source.extractfile(member)
                        if extracted is None:
                            raise ModulePackageError(f'Frontend archive member "{normalized}" is unreadable.')
                        with target.open("xb") as destination:
                            shutil.copyfileobj(extracted, destination)
                    else:
                        raise ModulePackageError("Frontend archives may contain only directories and regular files.")
        except (OSError, tarfile.TarError) as exc:
            raise ModulePackageError(f"The frontend artifact is not a safe tar archive: {exc}") from exc

    def _verify_frontend_definition(
        self,
        module_root: Path,
        package: VerifiedModulePackage,
    ) -> None:
        definition_path = module_root / "module.json"
        if definition_path.is_symlink() or not definition_path.is_file():
            raise ModulePackageError("Frontend artifact must contain module.json at its root.")
        try:
            definition = json.loads(definition_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModulePackageError("Frontend module.json is not valid JSON.") from exc
        if definition.get("id") != package.module_id:
            raise ModulePackageError("Frontend module ID does not match package metadata.")
        if definition.get("version") != package.version:
            raise ModulePackageError("Frontend module version does not match package metadata.")
        backend_id = definition.get("backendModuleId")
        if backend_id is not None and (backend_id != package.module_id or package.backend is None):
            raise ModulePackageError("Frontend backendModuleId requires the same packaged backend module.")

    def _required_entry(self, lock: ModulesLock, module_id: str) -> ModuleLockEntry:
        entry = next((item for item in lock.modules if item.id == module_id), None)
        if entry is None:
            raise ModuleEnableError(f'Module "{module_id}" is not installed.')
        return entry

    def _reject_builtin_collision(self, module_id: str) -> None:
        builtins = {
            definition.declared_id
            for definition in FirstPartyModuleDiscovery(
                excluded_module_ids=self.excluded_builtin_module_ids
            ).discover_available()
        }
        if module_id in builtins:
            raise ModuleInstallConflictError(
                f'Module ID "{module_id}" already belongs to a built-in module.'
            )

    def _version_root(self, module_id: str, version: str) -> Path:
        return self.root / "installed" / module_id / version

    @contextmanager
    def _transaction_lock(self):
        self.root.mkdir(parents=True, exist_ok=True)
        lock_file = self.root / ".modules.lock.lock"
        with lock_file.open("a+b") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _lock_entry(package: VerifiedModulePackage, *, enabled: bool) -> ModuleLockEntry:
    return ModuleLockEntry(
        id=package.module_id,
        version=package.version,
        enabled=enabled,
        publisher=package.publisher,
        source=package.source,
        provenance=package.provenance,
        artifact=package.artifact.model_copy(
            update={"sha256": package.bundle_sha256 or package.artifact.sha256}
        ),
        backend=LockedComponent(
            present=package.backend is not None,
            artifact=None if package.backend is None else package.backend.artifact,
            sha256=None if package.backend is None else package.backend.sha256,
        ),
        frontend=LockedComponent(
            present=package.frontend is not None,
            artifact=None if package.frontend is None else package.frontend.artifact,
            sha256=None if package.frontend is None else package.frontend.sha256,
        ),
    )


def _replace_entry(lock: ModulesLock, entry: ModuleLockEntry) -> ModulesLock:
    return ModulesLock(
        modules=tuple(
            sorted(
                (entry if item.id == entry.id else item for item in lock.modules),
                key=lambda item: item.id,
            )
        )
    )


def _validate_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or "\x00" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or value != path.as_posix()
    ):
        raise ValueError("artifact paths must be normalized relative POSIX paths")
    return path


def _safe_input_file(root: Path, relative_path: str) -> Path:
    try:
        relative = _validate_relative_path(relative_path)
    except ValueError as exc:
        raise ModulePackageError(str(exc)) from exc
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ModulePackageError("Package artifact paths may not traverse symbolic links.")
    resolved = current.resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ModulePackageError(f'Package artifact "{relative_path}" is not a regular local file.')
    return resolved


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _purge_modules_from_path(path: Path) -> None:
    root = path.resolve()
    for name, module in tuple(sys.modules.items()):
        source = getattr(module, "__file__", None)
        if source is None:
            continue
        try:
            if Path(source).resolve().is_relative_to(root):
                sys.modules.pop(name, None)
        except OSError:
            continue


def installed_backend_distribution_paths(
    root: Path,
    *,
    lock: ModulesLock | None = None,
    enabled_only: bool = False,
) -> tuple[Path, ...]:
    """Resolve backend roots from authoritative install state without activation."""

    install_root = root.resolve()
    active_lock = lock or read_modules_lock(install_root / "modules.lock")
    return tuple(
        install_root / "installed" / entry.id / entry.version / "backend/site-packages"
        for entry in active_lock.modules
        if entry.backend.present and (entry.enabled or not enabled_only)
    )
