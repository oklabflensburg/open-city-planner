"""Strict registry-v1 resolution and bounded OCP bundle downloads."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Literal, Self
from urllib.parse import unquote, urljoin, urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.platform.modules.bundle import BUNDLE_FORMAT_VERSION, MAX_BUNDLE_ARCHIVE_SIZE
from app.platform.modules.installer import Digest, ModuleId, VerifiedModulePackage
from app.platform.modules.manifest import SemanticVersion, SemanticVersionRange, parse_manifest

DEFAULT_REGISTRY_URL = "https://packages.stadtplaner.oklabflensburg.de"
REGISTRY_URL_ENV = "OCP_MODULE_REGISTRY_URL"
REGISTRY_SCHEMA_VERSION = 1
MAX_REGISTRY_DOCUMENT_SIZE = 1024 * 1024
MAX_REGISTRY_REDIRECTS = 5
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
CONNECT_TIMEOUT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 30.0

RegistryChannel = Literal["stable", "beta", "nightly"]
Classification = Literal["first-party", "reviewed-community"]


class ModuleRegistryError(RuntimeError):
    """Base error for registry resolution and downloads."""


class ModuleRegistryValidationError(ModuleRegistryError):
    """Registry data or a requested selection is invalid."""


class ModuleRegistryHTTPError(ModuleRegistryError):
    """A bounded registry HTTP operation failed."""


class ModuleRegistryIntegrityError(ModuleRegistryError):
    """Downloaded bytes do not match immutable registry metadata."""


class _StrictRegistryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RegistryPublisher(_StrictRegistryModel):
    id: ModuleId
    name: str = Field(min_length=1, max_length=120)


class RegistryChannelRelease(_StrictRegistryModel):
    version: SemanticVersion
    sha256: Digest


class RegistryChannels(_StrictRegistryModel):
    stable: RegistryChannelRelease | None = None
    beta: RegistryChannelRelease | None = None
    nightly: RegistryChannelRelease | None = None

    def get(self, channel: RegistryChannel) -> RegistryChannelRelease | None:
        return getattr(self, channel)


class RegistryIndexModule(_StrictRegistryModel):
    id: ModuleId
    name: str = Field(min_length=1, max_length=120)
    publisher: RegistryPublisher
    classification: Classification
    channels: RegistryChannels
    metadata: str = Field(min_length=1, max_length=512)


class RegistryIndex(_StrictRegistryModel):
    schema_version: Literal[REGISTRY_SCHEMA_VERSION]
    modules: tuple[RegistryIndexModule, ...]

    @model_validator(mode="after")
    def module_ids_are_unique(self) -> RegistryIndex:
        ids = [module.id for module in self.modules]
        if len(ids) != len(set(ids)):
            raise ValueError("registry index module IDs must be unique")
        return self


class RegistryArtifact(_StrictRegistryModel):
    url: str = Field(min_length=1, max_length=2048)
    sha256: Digest


class RegistryRequirements(_StrictRegistryModel):
    host: SemanticVersionRange
    sdk: SemanticVersionRange
    modules: dict[ModuleId, SemanticVersionRange]


class RegistryVersion(_StrictRegistryModel):
    version: SemanticVersion
    channel: RegistryChannel
    artifact: RegistryArtifact
    bundle_format_version: Literal[BUNDLE_FORMAT_VERSION]
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
    source_tag: str | None = Field(default=None, min_length=1, max_length=255)
    requires: RegistryRequirements


class RegistryModuleMetadata(_StrictRegistryModel):
    schema_version: Literal[REGISTRY_SCHEMA_VERSION]
    id: ModuleId
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1, max_length=1000)
    publisher: RegistryPublisher
    classification: Classification
    source_repository: str = Field(min_length=1, max_length=512)
    license: str = Field(min_length=1, max_length=255)
    homepage: str | None = Field(default=None, min_length=1, max_length=2048)
    documentation_url: str | None = Field(default=None, min_length=1, max_length=2048)
    versions: tuple[RegistryVersion, ...] = Field(min_length=1)

    @field_validator("source_repository", "homepage", "documentation_url")
    @classmethod
    def public_urls_are_https(cls, value: str | None) -> str | None:
        if value is not None:
            parsed = _validate_network_url(
                value, allow_http=False, description="Registry metadata URL"
            )
            if parsed.query or parsed.fragment:
                raise ValueError("Registry metadata URLs must not contain query or fragment")
        return value

    @model_validator(mode="after")
    def versions_are_unique(self) -> RegistryModuleMetadata:
        versions = [release.version for release in self.versions]
        if len(versions) != len(set(versions)):
            raise ValueError("registry module versions must be unique")
        return self


class ResolvedRegistryRelease(_StrictRegistryModel):
    module_id: ModuleId
    version: SemanticVersion
    channel: RegistryChannel
    sha256: Digest
    artifact_url: str
    publisher: str
    classification: Classification
    source_repository: str
    source_commit: str
    source_tag: str | None
    license: str
    requirements: RegistryRequirements
    bundle_format_version: Literal[BUNDLE_FORMAT_VERSION]


class DownloadedRegistryBundle(_StrictRegistryModel):
    release: ResolvedRegistryRelease
    path: Path
    sha256: Digest


class ModuleRegistryClient:
    """Load registry v1 on explicit CLI use; never part of application startup."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        allow_http_for_tests: bool = False,
        max_bundle_size: int = MAX_BUNDLE_ARCHIVE_SIZE,
        max_redirects: int = MAX_REGISTRY_REDIRECTS,
    ) -> None:
        configured = base_url or os.environ.get(REGISTRY_URL_ENV) or DEFAULT_REGISTRY_URL
        parsed = _validate_network_url(
            configured.rstrip("/"),
            allow_http=allow_http_for_tests,
            description="Registry base URL",
        )
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ModuleRegistryValidationError(
                "Registry base URL must not contain a path, query, or fragment."
            )
        if max_bundle_size <= 0 or max_redirects < 0:
            raise ValueError("registry download limits must be positive")
        self.base_url = configured.rstrip("/")
        self.allow_http_for_tests = allow_http_for_tests
        self.max_bundle_size = max_bundle_size
        self.max_redirects = max_redirects
        self._client = httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(
                connect=CONNECT_TIMEOUT_SECONDS,
                read=READ_TIMEOUT_SECONDS,
                write=READ_TIMEOUT_SECONDS,
                pool=CONNECT_TIMEOUT_SECONDS,
            ),
            follow_redirects=False,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def resolve(
        self,
        module_id: str,
        *,
        version: str | None = None,
        channel: RegistryChannel | None = None,
        expected_sha256: str | None = None,
    ) -> ResolvedRegistryRelease:
        if version is not None and channel is not None:
            raise ModuleRegistryValidationError(
                "Version and channel are mutually exclusive registry selections."
            )
        if channel not in {None, "stable", "beta", "nightly"}:
            raise ModuleRegistryValidationError(f'Unknown Registry channel "{channel}".')
        try:
            requested_id = _RequestedModuleId(id=module_id).id
            requested_version = (
                None if version is None else _RequestedVersion(version=version).version
            )
            deployment_digest = (
                None if expected_sha256 is None else _RequestedDigest(sha256=expected_sha256).sha256
            )
        except ValidationError as exc:
            raise ModuleRegistryValidationError(f"Invalid registry selection: {exc}") from exc

        selected_channel: RegistryChannel = channel or "stable"
        index = self._load_model(f"{self.base_url}/index.json", RegistryIndex, "registry index")
        index_module = next((item for item in index.modules if item.id == requested_id), None)
        if index_module is None:
            raise ModuleRegistryValidationError(
                f'Module "{requested_id}" is not present in the registry.'
            )
        metadata_url = self._metadata_url(index_module.metadata, requested_id)
        metadata = self._load_model(
            metadata_url, RegistryModuleMetadata, f'metadata for module "{requested_id}"'
        )
        self._validate_module_consistency(index_module, metadata)

        pointer: RegistryChannelRelease | None = None
        if requested_version is None:
            pointer = index_module.channels.get(selected_channel)
            if pointer is None:
                raise ModuleRegistryValidationError(
                    f'Channel "{selected_channel}" is not available for module "{requested_id}".'
                )
            requested_version = pointer.version
        release = next(
            (item for item in metadata.versions if item.version == requested_version),
            None,
        )
        if release is None:
            raise ModuleRegistryValidationError(
                f'Version "{requested_version}" is not available for module "{requested_id}".'
            )
        if pointer is not None:
            if release.channel != selected_channel or release.version != pointer.version:
                raise ModuleRegistryValidationError(
                    "Registry index channel conflicts with module metadata."
                )
            if release.artifact.sha256 != pointer.sha256:
                raise ModuleRegistryIntegrityError(
                    "Registry index digest conflicts with module metadata."
                )
        elif (matching_pointer := index_module.channels.get(release.channel)) is not None:
            if (
                matching_pointer.version == release.version
                and matching_pointer.sha256 != release.artifact.sha256
            ):
                raise ModuleRegistryIntegrityError(
                    "Registry index digest conflicts with module metadata."
                )
        if deployment_digest is not None and deployment_digest != release.artifact.sha256:
            raise ModuleRegistryIntegrityError(
                "Expected deployment SHA-256 conflicts with the registry digest."
            )
        self._artifact_url(
            release.artifact.url,
            requested_id,
            release.version,
            metadata.source_repository,
        )
        return ResolvedRegistryRelease(
            module_id=requested_id,
            version=release.version,
            channel=release.channel,
            sha256=release.artifact.sha256,
            artifact_url=release.artifact.url,
            publisher=metadata.publisher.id,
            classification=metadata.classification,
            source_repository=metadata.source_repository,
            source_commit=release.source_commit,
            source_tag=release.source_tag,
            license=metadata.license,
            requirements=release.requires,
            bundle_format_version=release.bundle_format_version,
        )

    @staticmethod
    def validate_bundle(
        release: ResolvedRegistryRelease,
        package: VerifiedModulePackage,
    ) -> None:
        """Bind Registry metadata to the already verified bundle handoff."""

        if package.module_id != release.module_id:
            raise ModuleRegistryValidationError(
                "Downloaded bundle module ID conflicts with Registry metadata."
            )
        if package.version != release.version:
            raise ModuleRegistryValidationError(
                "Downloaded bundle version conflicts with Registry metadata."
            )
        if package.publisher != release.publisher:
            raise ModuleRegistryValidationError(
                "Downloaded bundle publisher conflicts with Registry metadata."
            )
        if package.provenance.source_repository != release.source_repository:
            raise ModuleRegistryValidationError(
                "Downloaded bundle source repository conflicts with Registry metadata."
            )
        if package.provenance.source_commit != release.source_commit:
            raise ModuleRegistryValidationError(
                "Downloaded bundle source commit conflicts with Registry metadata."
            )
        if package.provenance.source_tag != release.source_tag:
            raise ModuleRegistryValidationError(
                "Downloaded bundle source tag conflicts with Registry metadata."
            )
        if package.provenance.license != release.license:
            raise ModuleRegistryValidationError(
                "Downloaded bundle license conflicts with Registry metadata."
            )
        manifest = parse_manifest(package.manifest)
        if (
            manifest.requires.host != release.requirements.host
            or manifest.requires.sdk != release.requirements.sdk
            or manifest.requires.modules != release.requirements.modules
        ):
            raise ModuleRegistryValidationError(
                "Downloaded bundle requirements conflict with Registry metadata."
            )
        if package.bundle_sha256 != release.sha256:
            raise ModuleRegistryIntegrityError(
                "Verified bundle SHA-256 conflicts with Registry metadata."
            )

    @contextmanager
    def download(self, release: ResolvedRegistryRelease) -> Iterator[DownloadedRegistryBundle]:
        with TemporaryDirectory(prefix="ocp-registry-") as temporary_root:
            temporary = Path(temporary_root) / f"{release.module_id}-{release.version}.ocp"
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            received = 0
            digest = hashlib.sha256()
            try:
                with os.fdopen(descriptor, "wb") as destination:
                    with self._stream(release.artifact_url) as response:
                        declared_length = _content_length(response)
                        if declared_length is not None and declared_length > self.max_bundle_size:
                            raise ModuleRegistryHTTPError(
                                "Registry bundle exceeds the download size limit."
                            )
                        for chunk in _response_bytes(response):
                            received += len(chunk)
                            if received > self.max_bundle_size:
                                raise ModuleRegistryHTTPError(
                                    "Registry bundle exceeds the download size limit."
                                )
                            destination.write(chunk)
                            digest.update(chunk)
                    destination.flush()
                    os.fsync(destination.fileno())
            except OSError as exc:
                raise ModuleRegistryHTTPError(
                    f"Registry bundle could not be stored safely: {exc}"
                ) from exc
            if declared_length is not None and received != declared_length:
                raise ModuleRegistryHTTPError(
                    "Registry bundle download is incomplete: Content-Length does not match."
                )
            actual_digest = digest.hexdigest()
            if actual_digest != release.sha256:
                raise ModuleRegistryIntegrityError(
                    "Downloaded bundle SHA-256 does not match the registry digest."
                )
            yield DownloadedRegistryBundle(
                release=release,
                path=temporary,
                sha256=actual_digest,
            )

    def _load_model(self, url: str, model: type[BaseModel], description: str):
        try:
            with self._stream(url) as response:
                payload = _read_bounded(response, MAX_REGISTRY_DOCUMENT_SIZE)
            # Decode once for duplicate-key detection, then validate from JSON so
            # strict tuple fields retain the same convention as modules.lock.
            json.loads(payload, object_pairs_hook=_unique_json_object)
            return model.model_validate_json(payload)
        except ModuleRegistryError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
            raise ModuleRegistryValidationError(f"Invalid {description}: {exc}") from exc

    @contextmanager
    def _stream(self, url: str) -> Iterator[httpx.Response]:
        current = url
        try:
            for redirect_count in range(self.max_redirects + 1):
                _validate_network_url(
                    current,
                    allow_http=self.allow_http_for_tests,
                    description="Registry request URL",
                )
                with self._client.stream("GET", current) as response:
                    if response.is_redirect:
                        if redirect_count == self.max_redirects:
                            raise ModuleRegistryHTTPError("Registry redirect limit exceeded.")
                        location = response.headers.get("location")
                        if not location:
                            raise ModuleRegistryHTTPError(
                                "Registry redirect is missing a Location header."
                            )
                        current = urljoin(current, location)
                        _validate_network_url(
                            current,
                            allow_http=self.allow_http_for_tests,
                            description="Registry redirect target",
                        )
                        continue
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        raise ModuleRegistryHTTPError(
                            f"Registry request failed with HTTP {response.status_code}."
                        ) from exc
                    yield response
                    return
            raise ModuleRegistryHTTPError("Registry redirect limit exceeded.")
        except ModuleRegistryError:
            raise
        except httpx.TimeoutException as exc:
            raise ModuleRegistryHTTPError("Registry request timed out.") from exc
        except httpx.HTTPError as exc:
            raise ModuleRegistryHTTPError(f"Registry request failed: {exc}") from exc

    def _metadata_url(self, reference: str, module_id: str) -> str:
        parsed = urlsplit(reference)
        decoded_path = unquote(parsed.path)
        path = PurePosixPath(decoded_path)
        if (
            parsed.scheme
            or parsed.netloc
            or parsed.query
            or parsed.fragment
            or "\\" in reference
            or "\x00" in reference
            or any(part in {"", ".", ".."} for part in path.parts)
            or decoded_path != f"/modules/{module_id}.json"
        ):
            raise ModuleRegistryValidationError(
                "Registry metadata reference must be a safe /modules/*.json path."
            )
        resolved = urljoin(f"{self.base_url}/", reference)
        if _origin(resolved) != _origin(self.base_url):
            raise ModuleRegistryValidationError(
                "Registry metadata reference must remain on the registry origin."
            )
        return resolved

    def _artifact_url(
        self,
        url: str,
        module_id: str,
        version: str,
        source_repository: str,
    ) -> None:
        parsed = _validate_network_url(
            url,
            allow_http=self.allow_http_for_tests,
            description="Registry artifact URL",
        )
        if parsed.query or parsed.fragment or not parsed.path.endswith(".ocp"):
            raise ModuleRegistryValidationError(
                "Registry artifact URL must identify an .ocp file without query or fragment."
            )
        registry_origin = _origin(self.base_url)
        if _origin(url) == registry_origin:
            expected = f"/modules/{module_id}/{version}/{module_id}-{version}.ocp"
            if parsed.path != expected:
                raise ModuleRegistryValidationError(
                    "Registry artifact URL is not the canonical versioned module path."
                )
        else:
            source = urlsplit(source_repository)
            release_prefix = f"{source.path.rstrip('/')}/releases/download/"
            if parsed.hostname != "github.com" or not parsed.path.startswith(release_prefix):
                raise ModuleRegistryValidationError(
                    "Registry artifacts must use the registry origin or the source repository's "
                    "versioned GitHub Release URL."
                )

    @staticmethod
    def _validate_module_consistency(
        index: RegistryIndexModule,
        metadata: RegistryModuleMetadata,
    ) -> None:
        if index.id != metadata.id:
            raise ModuleRegistryValidationError(
                "Registry index module ID conflicts with module metadata."
            )
        if index.publisher != metadata.publisher:
            raise ModuleRegistryValidationError(
                "Registry index publisher conflicts with module metadata."
            )
        if index.classification != metadata.classification:
            raise ModuleRegistryValidationError(
                "Registry index classification conflicts with module metadata."
            )


class _RequestedModuleId(_StrictRegistryModel):
    id: ModuleId


class _RequestedVersion(_StrictRegistryModel):
    version: SemanticVersion


class _RequestedDigest(_StrictRegistryModel):
    sha256: Digest


def _validate_network_url(
    value: str,
    *,
    allow_http: bool,
    description: str,
):
    try:
        parsed = urlsplit(value)
        _port = parsed.port
    except ValueError as exc:
        raise ModuleRegistryValidationError(f"{description} is not a valid URL.") from exc
    allowed_schemes = {"https", "http"} if allow_http else {"https"}
    if (
        parsed.scheme not in allowed_schemes
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        scheme = "HTTP(S)" if allow_http else "HTTPS"
        raise ModuleRegistryValidationError(
            f"{description} must use {scheme} without embedded credentials."
        )
    return parsed


def _origin(value: str) -> tuple[str, str, int | None]:
    parsed = urlsplit(value)
    return parsed.scheme, parsed.hostname or "", parsed.port


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ModuleRegistryValidationError(
                f'Duplicate registry JSON key "{key}" is forbidden.'
            )
        result[key] = value
    return result


def _content_length(response: httpx.Response) -> int | None:
    # HTTPX transparently decodes Content-Encoding. Its Content-Length then
    # describes the encoded transfer rather than the artifact bytes we persist.
    if response.headers.get("content-encoding"):
        return None
    value = response.headers.get("content-length")
    if value is None:
        return None
    try:
        length = int(value)
    except ValueError as exc:
        raise ModuleRegistryHTTPError("Registry response has an invalid Content-Length.") from exc
    if length < 0:
        raise ModuleRegistryHTTPError("Registry response has an invalid Content-Length.")
    return length


def _read_bounded(response: httpx.Response, limit: int) -> bytes:
    declared_length = _content_length(response)
    if declared_length is not None and declared_length > limit:
        raise ModuleRegistryHTTPError("Registry document exceeds the size limit.")
    payload = bytearray()
    for chunk in _response_bytes(response):
        payload.extend(chunk)
        if len(payload) > limit:
            raise ModuleRegistryHTTPError("Registry document exceeds the size limit.")
    if declared_length is not None and len(payload) != declared_length:
        raise ModuleRegistryHTTPError(
            "Registry document download is incomplete: Content-Length does not match."
        )
    return bytes(payload)


def _response_bytes(response: httpx.Response) -> Iterator[bytes]:
    yield from response.iter_bytes(DOWNLOAD_CHUNK_SIZE)
