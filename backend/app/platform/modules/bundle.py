"""Versioned, passive and deterministic OCP module release bundles."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import zipfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.platform.modules.errors import ModuleManifestError
from app.platform.modules.installer import (
    LOCAL_PACKAGE_INPUT_FILENAME,
    Digest,
    LockedArtifact,
    ModuleId,
    ModulePackageError,
    ModuleProvenance,
    ModuleSource,
    PackageComponentInput,
    VerifiedModulePackage,
    calculate_package_digest,
)
from app.platform.modules.manifest import SemanticVersion, parse_manifest

BUNDLE_FORMAT_VERSION = 1
BUNDLE_METADATA_PATH = "module.yaml"
BUNDLE_CHECKSUMS_PATH = "checksums.json"
MAX_BUNDLE_FILES = 32
MAX_BUNDLE_FILE_SIZE = 256 * 1024 * 1024
MAX_BUNDLE_UNCOMPRESSED_SIZE = 512 * 1024 * 1024
MAX_BUNDLE_ARCHIVE_SIZE = 512 * 1024 * 1024
MAX_BUNDLE_COMPRESSION_RATIO = 200
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_ALLOWED_DIRECTORIES = frozenset({"backend", "frontend"})


class ModuleBundleError(ModulePackageError):
    """Base error for an invalid local OCP bundle."""


class ModuleBundleFormatError(ModuleBundleError):
    """The bundle structure or metadata schema is unsupported."""


class ModuleBundleIntegrityError(ModuleBundleError):
    """The bundle payload does not match its integrity metadata."""


class _StrictBundleModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class BundleComponent(_StrictBundleModel):
    artifact: str = Field(min_length=1, max_length=512)


class ModuleBundleMetadata(_StrictBundleModel):
    bundle_format_version: Literal[BUNDLE_FORMAT_VERSION]
    module_id: ModuleId
    version: SemanticVersion
    publisher: str = Field(min_length=1, max_length=255)
    source: ModuleSource
    provenance: ModuleProvenance
    manifest: dict[str, object]
    backend: BundleComponent | None = None
    frontend: BundleComponent | None = None

    @model_validator(mode="after")
    def has_payload(self) -> ModuleBundleMetadata:
        if self.backend is None and self.frontend is None:
            raise ValueError("an OCP bundle requires a backend or frontend artifact")
        return self


class BundleChecksums(_StrictBundleModel):
    algorithm: Literal["sha256"]
    files: dict[str, Digest]


class _UniqueKeySafeLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    result: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as exc:
            raise ModuleBundleFormatError("YAML mapping keys must be scalar values.") from exc
        if duplicate:
            raise ModuleBundleFormatError(f'Duplicate YAML key "{key}" is forbidden.')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def bundle_sha256(path: Path) -> str:
    return _sha256_file(path)


def load_bundle_manifest(path: Path) -> dict[str, object]:
    """Safely decode a JSON or YAML module manifest for the bundle builder."""

    try:
        decoded = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeySafeLoader)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ModuleBundleFormatError(f"The module manifest input is invalid: {exc}") from exc
    if not isinstance(decoded, dict) or not all(isinstance(key, str) for key in decoded):
        raise ModuleBundleFormatError("The module manifest input must be a string-keyed mapping.")
    return decoded


def build_ocp_bundle(
    output: Path,
    *,
    manifest: Mapping[str, object],
    publisher: str,
    source: ModuleSource,
    provenance: ModuleProvenance,
    backend_artifact: Path | None = None,
    frontend_artifact: Path | None = None,
) -> str:
    """Build one deterministic OCP v1 ZIP and return its immutable file digest."""

    if output.suffix != ".ocp":
        raise ModuleBundleFormatError('Bundle output must use the ".ocp" extension.')
    try:
        parsed_manifest = parse_manifest(manifest, origin=str(output))
    except ModuleManifestError as exc:
        raise ModuleBundleFormatError(str(exc)) from exc
    if (backend_artifact is None) != (parsed_manifest.backend is None):
        raise ModuleBundleFormatError(
            "Backend artifact presence must match the transported module manifest."
        )
    if (frontend_artifact is None) != (parsed_manifest.frontend is None):
        raise ModuleBundleFormatError(
            "Frontend artifact presence must match the transported module manifest."
        )

    payloads: dict[str, bytes] = {}
    if backend_artifact is not None:
        if backend_artifact.suffix != ".whl":
            raise ModuleBundleFormatError("Backend bundle artifacts must be wheels.")
        payloads[f"backend/{backend_artifact.name}"] = _read_local_artifact(
            backend_artifact
        )
    if frontend_artifact is not None:
        if not frontend_artifact.name.endswith(".tgz"):
            raise ModuleBundleFormatError('Frontend bundle artifacts must use ".tgz".')
        payloads[f"frontend/{frontend_artifact.name}"] = _read_local_artifact(
            frontend_artifact
        )

    metadata = ModuleBundleMetadata(
        bundle_format_version=BUNDLE_FORMAT_VERSION,
        module_id=parsed_manifest.id,
        version=parsed_manifest.version,
        publisher=publisher,
        source=source,
        provenance=provenance,
        manifest=parsed_manifest.model_dump(mode="json", by_alias=True),
        backend=(
            None
            if backend_artifact is None
            else BundleComponent(artifact=f"backend/{backend_artifact.name}")
        ),
        frontend=(
            None
            if frontend_artifact is None
            else BundleComponent(artifact=f"frontend/{frontend_artifact.name}")
        ),
    )
    checksums = BundleChecksums(
        algorithm="sha256",
        files={name: _sha256_bytes(payload) for name, payload in sorted(payloads.items())},
    )
    members = {
        BUNDLE_METADATA_PATH: _serialize_bundle_metadata(metadata),
        **payloads,
        BUNDLE_CHECKSUMS_PATH: _serialize_checksums(checksums),
    }
    _validate_declared_bundle(metadata, checksums, members)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            strict_timestamps=True,
        ) as archive:
            for name in _ordered_member_names(members):
                info = zipfile.ZipInfo(name, date_time=_ZIP_TIMESTAMP)
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(info, members[name], compress_type=zipfile.ZIP_DEFLATED)
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return bundle_sha256(output)


def read_ocp_bundle(bundle_path: Path, staging_directory: Path) -> VerifiedModulePackage:
    """Validate and stage one local OCP bundle as the existing installer handoff."""

    path = bundle_path.resolve()
    if path.suffix != ".ocp" or path.is_symlink() or not path.is_file():
        raise ModuleBundleFormatError("Bundle input must be a regular local .ocp file.")
    try:
        if path.stat().st_size > MAX_BUNDLE_ARCHIVE_SIZE:
            raise ModuleBundleFormatError("OCP bundle exceeds the compressed size limit.")
    except OSError as exc:
        raise ModuleBundleFormatError(f"OCP bundle metadata could not be read: {exc}") from exc

    try:
        with zipfile.ZipFile(path) as archive:
            members = _inspect_archive(archive)
            metadata_bytes = _read_member(archive, members[BUNDLE_METADATA_PATH])
            checksums_bytes = _read_member(archive, members[BUNDLE_CHECKSUMS_PATH])
            metadata = _parse_bundle_metadata(metadata_bytes)
            checksums = _parse_checksums(checksums_bytes)
            payload_paths = _declared_payload_paths(metadata)
            _validate_member_set(members, payload_paths)
            _validate_checksums(checksums, payload_paths)

            payloads: dict[str, bytes] = {}
            for payload_path in payload_paths:
                payload = _read_member(archive, members[payload_path])
                if _sha256_bytes(payload) != checksums.files[payload_path]:
                    raise ModuleBundleIntegrityError(
                        f'Bundle payload SHA-256 mismatch for "{payload_path}".'
                    )
                payloads[payload_path] = payload
    except ModuleBundleError:
        raise
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise ModuleBundleFormatError(f"The OCP bundle is not a valid ZIP archive: {exc}") from exc

    try:
        manifest = parse_manifest(
            metadata.manifest,
            origin=f"{path}:{BUNDLE_METADATA_PATH}",
        )
    except ModuleManifestError as exc:
        raise ModuleBundleFormatError(str(exc)) from exc
    if metadata.module_id != manifest.id:
        raise ModuleBundleFormatError("Bundle module_id does not match the transported manifest ID.")
    if metadata.version != manifest.version:
        raise ModuleBundleFormatError("Bundle version does not match the transported manifest version.")
    if (metadata.backend is None) != (manifest.backend is None):
        raise ModuleBundleFormatError(
            "Backend artifact presence does not match the transported manifest."
        )
    if (metadata.frontend is None) != (manifest.frontend is None):
        raise ModuleBundleFormatError(
            "Frontend artifact presence does not match the transported manifest."
        )

    staging_root = staging_directory.resolve()
    staging_root.mkdir(parents=True, exist_ok=True)
    components: dict[str, PackageComponentInput | None] = {
        "backend": None,
        "frontend": None,
    }
    for component_name, component in (
        ("backend", metadata.backend),
        ("frontend", metadata.frontend),
    ):
        if component is None:
            continue
        payload = payloads[component.artifact]
        target = staging_root.joinpath(*PurePosixPath(component.artifact).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        components[component_name] = PackageComponentInput(
            path=component.artifact,
            artifact=PurePosixPath(component.artifact).name,
            sha256=checksums.files[component.artifact],
        )

    backend = components["backend"]
    frontend = components["frontend"]
    package = VerifiedModulePackage(
        module_id=metadata.module_id,
        version=metadata.version,
        publisher=metadata.publisher,
        source=metadata.source,
        provenance=metadata.provenance,
        artifact=LockedArtifact(
            identifier=path.name,
            sha256=calculate_package_digest(
                None
                if backend is None
                else (backend.artifact, payloads[backend.path]),
                None
                if frontend is None
                else (frontend.artifact, payloads[frontend.path]),
            ),
        ),
        bundle_sha256=bundle_sha256(path),
        manifest=manifest.model_dump(mode="json", by_alias=True),
        backend=backend,
        frontend=frontend,
    )
    (staging_root / LOCAL_PACKAGE_INPUT_FILENAME).write_text(
        package.model_dump_json(),
        encoding="utf-8",
    )
    return package


@contextmanager
def staged_ocp_bundle(bundle_path: Path) -> Iterator[tuple[Path, VerifiedModulePackage]]:
    """Keep staged payloads alive only while the authoritative installer consumes them."""

    with TemporaryDirectory(prefix="ocp-bundle-") as temporary:
        root = Path(temporary)
        package = read_ocp_bundle(bundle_path, root)
        yield root, package


def _inspect_archive(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    infos = archive.infolist()
    if len(infos) > MAX_BUNDLE_FILES:
        raise ModuleBundleFormatError("OCP bundle contains too many archive members.")
    members: dict[str, zipfile.ZipInfo] = {}
    total_size = 0
    for info in infos:
        name = info.filename.rstrip("/")
        if not name:
            raise ModuleBundleFormatError("OCP bundle contains an empty archive path.")
        normalized = _validate_bundle_path(name).as_posix()
        if normalized in members:
            raise ModuleBundleFormatError(
                f'Duplicate OCP bundle path "{normalized}" is forbidden.'
            )
        mode = info.external_attr >> 16
        if info.is_dir():
            if normalized not in _ALLOWED_DIRECTORIES:
                raise ModuleBundleFormatError(
                    f'Unknown OCP bundle directory "{normalized}".'
                )
        else:
            file_type = stat.S_IFMT(mode)
            if file_type not in {0, stat.S_IFREG}:
                raise ModuleBundleFormatError("OCP bundles may contain only regular files.")
            if info.flag_bits & 0x1:
                raise ModuleBundleFormatError("Encrypted OCP bundle members are forbidden.")
            if info.file_size > MAX_BUNDLE_FILE_SIZE:
                raise ModuleBundleFormatError(
                    f'OCP bundle member "{normalized}" exceeds the file size limit.'
                )
            total_size += info.file_size
            if total_size > MAX_BUNDLE_UNCOMPRESSED_SIZE:
                raise ModuleBundleFormatError(
                    "OCP bundle exceeds the total uncompressed size limit."
                )
            if (
                info.file_size > 1024 * 1024
                and (
                    info.compress_size == 0
                    or info.file_size / info.compress_size > MAX_BUNDLE_COMPRESSION_RATIO
                )
            ):
                raise ModuleBundleFormatError(
                    f'OCP bundle member "{normalized}" exceeds the compression ratio limit.'
                )
        members[normalized] = info
    return members


def _validate_bundle_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or "\x00" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or value != path.as_posix()
    ):
        raise ModuleBundleFormatError(
            "OCP bundle paths must be normalized relative POSIX paths."
        )
    root = path.parts[0]
    if len(path.parts) == 1:
        if root not in {BUNDLE_METADATA_PATH, BUNDLE_CHECKSUMS_PATH, *_ALLOWED_DIRECTORIES}:
            raise ModuleBundleFormatError(f'Unknown OCP bundle root "{root}".')
    elif root not in _ALLOWED_DIRECTORIES or len(path.parts) != 2:
        raise ModuleBundleFormatError(f'Unknown OCP bundle payload path "{value}".')
    return path


def _read_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    with archive.open(info) as stream:
        payload = stream.read(MAX_BUNDLE_FILE_SIZE + 1)
    if len(payload) > MAX_BUNDLE_FILE_SIZE:
        raise ModuleBundleFormatError(
            f'OCP bundle member "{info.filename}" exceeds the file size limit.'
        )
    return payload


def _parse_bundle_metadata(payload: bytes) -> ModuleBundleMetadata:
    try:
        decoded = yaml.load(payload.decode("utf-8"), Loader=_UniqueKeySafeLoader)
        return ModuleBundleMetadata.model_validate(decoded)
    except ModuleBundleError:
        raise
    except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise ModuleBundleFormatError(f"Invalid module.yaml: {exc}") from exc


def _parse_checksums(payload: bytes) -> BundleChecksums:
    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ModuleBundleFormatError(
                    f'Duplicate checksums.json key "{key}" is forbidden.'
                )
            result[key] = value
        return result

    try:
        decoded = json.loads(payload, object_pairs_hook=unique_object)
        return BundleChecksums.model_validate(decoded)
    except ModuleBundleError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        raise ModuleBundleFormatError(f"Invalid checksums.json: {exc}") from exc


def _declared_payload_paths(metadata: ModuleBundleMetadata) -> tuple[str, ...]:
    paths = tuple(
        component.artifact
        for component in (metadata.backend, metadata.frontend)
        if component is not None
    )
    for path in paths:
        normalized = _validate_bundle_path(path)
        if normalized.parts[0] == "backend" and not path.endswith(".whl"):
            raise ModuleBundleFormatError("Backend bundle artifacts must be wheels.")
        if normalized.parts[0] == "frontend" and not path.endswith(".tgz"):
            raise ModuleBundleFormatError('Frontend bundle artifacts must use ".tgz".')
    if len(paths) != len(set(paths)):
        raise ModuleBundleFormatError("Bundle components must use distinct artifact paths.")
    return tuple(sorted(paths))


def _validate_member_set(
    members: Mapping[str, zipfile.ZipInfo],
    payload_paths: tuple[str, ...],
) -> None:
    files = {name for name, info in members.items() if not info.is_dir()}
    expected = {BUNDLE_METADATA_PATH, BUNDLE_CHECKSUMS_PATH, *payload_paths}
    missing = sorted(expected.difference(files))
    if missing:
        raise ModuleBundleFormatError(f'Missing OCP bundle member "{missing[0]}".')
    unknown = sorted(files.difference(expected))
    if unknown:
        raise ModuleBundleFormatError(f'Undeclared OCP bundle member "{unknown[0]}".')


def _validate_checksums(
    checksums: BundleChecksums,
    payload_paths: tuple[str, ...],
) -> None:
    for path in checksums.files:
        _validate_bundle_path(path)
    declared = set(payload_paths)
    actual = set(checksums.files)
    if actual != declared:
        missing = sorted(declared.difference(actual))
        unknown = sorted(actual.difference(declared))
        detail = missing[0] if missing else unknown[0]
        raise ModuleBundleIntegrityError(
            f'Checksums must cover exactly the declared payloads; mismatch at "{detail}".'
        )


def _validate_declared_bundle(
    metadata: ModuleBundleMetadata,
    checksums: BundleChecksums,
    members: Mapping[str, bytes],
) -> None:
    payload_paths = _declared_payload_paths(metadata)
    if set(checksums.files) != set(payload_paths):
        raise ModuleBundleIntegrityError("Builder checksums do not match bundle payloads.")
    if set(members) != {BUNDLE_METADATA_PATH, BUNDLE_CHECKSUMS_PATH, *payload_paths}:
        raise ModuleBundleFormatError("Builder member set does not match bundle metadata.")


def _ordered_member_names(members: Mapping[str, bytes]) -> tuple[str, ...]:
    payloads = sorted(
        name
        for name in members
        if name not in {BUNDLE_METADATA_PATH, BUNDLE_CHECKSUMS_PATH}
    )
    return (BUNDLE_METADATA_PATH, *payloads, BUNDLE_CHECKSUMS_PATH)


def _serialize_bundle_metadata(metadata: ModuleBundleMetadata) -> bytes:
    return yaml.safe_dump(
        metadata.model_dump(mode="json"),
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=1_000_000,
    ).encode("utf-8")


def _serialize_checksums(checksums: BundleChecksums) -> bytes:
    return (
        json.dumps(
            checksums.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _read_local_artifact(path: Path) -> bytes:
    resolved = path.resolve()
    if path.is_symlink() or not resolved.is_file():
        raise ModuleBundleFormatError("Bundle artifacts must be regular local files.")
    if resolved.stat().st_size > MAX_BUNDLE_FILE_SIZE:
        raise ModuleBundleFormatError("Bundle artifact exceeds the file size limit.")
    return resolved.read_bytes()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
