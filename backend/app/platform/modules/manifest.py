"""Manifest Schema V1 und reine Compatibility-Validierung.

Der Contract verarbeitet bereits dekodierte Mappings. Dateizugriff, YAML-Loader,
Package-Discovery und Runtime-Aktivierung gehören bewusst nicht in dieses Modul.
"""

from collections.abc import Mapping, Sequence
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    WithJsonSchema,
    field_validator,
    model_validator,
)
from semantic_version import SimpleSpec, Version

from app.platform.modules.errors import (
    DuplicateConfigNamespaceError,
    DuplicateModuleIdError,
    DuplicatePersistenceSchemaError,
    InvalidRuntimeVersionError,
    MissingModuleDependencyError,
    ModuleCompatibilityError,
    ModuleDependencyVersionError,
    ModuleManifestError,
    ModuleSelfDependencyError,
    UnsupportedManifestVersionError,
)

MANIFEST_VERSION = 1
MODULE_ID_PATTERN = r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"
NAMESPACED_ID_PATTERN = (
    r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*)+$"
)
PYTHON_PACKAGE_PATTERN = r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$"
NPM_PACKAGE_PATTERN = r"^(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*$"
POSTGRES_IDENTIFIER_PATTERN = r"^[a-z][a-z0-9_]*$"
VERSION_OPERATORS = (">=", "<=", "==", "!=", ">", "<")


def _validate_semver(value: str) -> str:
    try:
        Version(value)
    except ValueError as exc:
        raise ValueError("must be a complete SemVer version such as 1.2.3") from exc
    return value


def _validate_version_range(value: str) -> str:
    if value != value.strip() or not value:
        raise ValueError("must be a non-empty canonical SemVer range without outer whitespace")

    clauses = value.split(",")
    for clause in clauses:
        if not clause or clause != clause.strip():
            raise ValueError("range clauses must be comma-separated without whitespace")
        operator = next(
            (candidate for candidate in VERSION_OPERATORS if clause.startswith(candidate)), None
        )
        if operator is None:
            raise ValueError(
                "range clauses must use one of >=, <=, ==, !=, > or < with a complete SemVer"
            )
        version_text = clause[len(operator) :]
        try:
            Version(version_text)
        except ValueError as exc:
            raise ValueError(
                f"range clause {clause!r} must contain a complete SemVer version"
            ) from exc

    try:
        SimpleSpec(value)
    except ValueError as exc:
        raise ValueError("must be a valid canonical SemVer range") from exc
    return value


type ModuleId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=False,
        min_length=1,
        max_length=63,
        pattern=MODULE_ID_PATTERN,
    ),
]
type NamespacedId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=False,
        min_length=3,
        max_length=127,
        pattern=NAMESPACED_ID_PATTERN,
    ),
]
type SemanticVersion = Annotated[
    str,
    StringConstraints(strip_whitespace=False, min_length=1, max_length=128),
    AfterValidator(_validate_semver),
    WithJsonSchema(
        {
            "type": "string",
            "format": "semver",
            "minLength": 1,
            "maxLength": 128,
            "examples": ["1.2.3"],
        }
    ),
]
type SemanticVersionRange = Annotated[
    str,
    StringConstraints(strip_whitespace=False, min_length=1, max_length=512),
    AfterValidator(_validate_version_range),
    WithJsonSchema(
        {
            "type": "string",
            "format": "semver-range",
            "minLength": 1,
            "maxLength": 512,
            "examples": [">=1.2.0,<2.0.0"],
        }
    ),
]


class StrictManifestModel(BaseModel):
    """Gemeinsame Strictness-Regeln aller Manifest-V1-Objekte."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ModuleRequirements(StrictManifestModel):
    """Pflichtkompatibilität und erforderliche Modulabhängigkeiten."""

    host: SemanticVersionRange
    sdk: SemanticVersionRange
    modules: dict[ModuleId, SemanticVersionRange] = Field(default_factory=dict)


class ModuleOptionalRequirements(StrictManifestModel):
    """Optionale Module, deren vorhandene Version dennoch kompatibel sein muss."""

    modules: dict[ModuleId, SemanticVersionRange] = Field(default_factory=dict)


class ModuleBackendPackage(StrictManifestModel):
    """Deklarativer Python-Distributionsname; keine Import-Anweisung."""

    package: str = Field(min_length=1, max_length=214, pattern=PYTHON_PACKAGE_PATTERN)


class ModuleFrontendPackage(StrictManifestModel):
    """Deklarativer npm-Paketname; kein Runtime-Bundle oder Download-Endpunkt."""

    package: str = Field(min_length=1, max_length=214, pattern=NPM_PACKAGE_PATTERN)


class ModuleConfig(StrictManifestModel):
    """Stabile Identität für das spätere Settings-Namespace aus #99."""

    namespace: ModuleId


class ModulePersistence(StrictManifestModel):
    """Deklarative Schema- und Migrations-Ownership aus #97."""

    schema_name: str = Field(
        alias="schema",
        min_length=1,
        max_length=63,
        pattern=POSTGRES_IDENTIFIER_PATTERN,
    )
    migrations: bool = False

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_by_alias=True,
        validate_by_name=False,
    )


class ModuleManifestV1(StrictManifestModel):
    """Versionierter, deklarativer Kernvertrag eines Open-City-Planner-Moduls."""

    manifest_version: Literal[1]
    id: ModuleId
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    version: SemanticVersion
    requires: ModuleRequirements
    optional: ModuleOptionalRequirements = Field(default_factory=ModuleOptionalRequirements)
    backend: ModuleBackendPackage | None = None
    frontend: ModuleFrontendPackage | None = None
    capabilities: list[NamespacedId] = Field(
        default_factory=list, json_schema_extra={"uniqueItems": True}
    )
    permissions: list[NamespacedId] = Field(
        default_factory=list, json_schema_extra={"uniqueItems": True}
    )
    config: ModuleConfig | None = None
    persistence: ModulePersistence | None = None

    @field_validator("capabilities", "permissions")
    @classmethod
    def identifiers_must_be_unique(cls, values: list[str]) -> list[str]:
        duplicates = sorted({value for value in values if values.count(value) > 1})
        if duplicates:
            raise ValueError(f"duplicate identifiers are forbidden: {', '.join(duplicates)}")
        return values

    @model_validator(mode="after")
    def validate_owned_identifiers(self) -> "ModuleManifestV1":
        permission_prefix = f"{self.id}."
        invalid_permissions = [
            permission for permission in self.permissions if not permission.startswith(permission_prefix)
        ]
        if invalid_permissions:
            raise ValueError(
                f'module permissions must start with "{permission_prefix}": '
                f"{', '.join(invalid_permissions)}"
            )
        overlapping_dependencies = sorted(
            set(self.requires.modules).intersection(self.optional.modules)
        )
        if overlapping_dependencies:
            raise ValueError(
                "module dependencies cannot be both required and optional: "
                f"{', '.join(overlapping_dependencies)}"
            )
        return self


type ManifestInput = Mapping[str, Any]


def parse_manifest(data: ManifestInput, *, origin: str | None = None) -> ModuleManifestV1:
    """Parse ein bereits sicher dekodiertes Mapping als Manifest Schema V1."""

    if not isinstance(data, Mapping):
        raise ModuleManifestError("Invalid module manifest: expected a decoded mapping.")
    manifest_version = data.get("manifest_version")
    if type(manifest_version) is not int or manifest_version != MANIFEST_VERSION:
        raise UnsupportedManifestVersionError(manifest_version, origin=origin)
    try:
        return ModuleManifestV1.model_validate(data)
    except ValidationError as exc:
        module_id = data.get("id") if isinstance(data.get("id"), str) else None
        location = f" from {origin}" if origin else ""
        raise ModuleManifestError(
            f"Invalid module manifest{location}: {exc}",
            module_id=module_id,
            origin=origin,
            details=exc.errors(include_url=False),
        ) from exc


def _runtime_version(value: str, target: str) -> Version:
    try:
        return Version(value)
    except ValueError as exc:
        raise InvalidRuntimeVersionError(target, value) from exc


def _matches(version: str, expected: str) -> bool:
    return Version(version) in SimpleSpec(expected)


def validate_manifest(
    manifest: ModuleManifestV1,
    *,
    host_version: str,
    sdk_version: str,
) -> ModuleManifestV1:
    """Isolierte Validierung eines Manifests gegen übergebene Host-/SDK-Versionen."""

    if manifest.id in manifest.requires.modules:
        raise ModuleSelfDependencyError(manifest.id, optional=False)
    if manifest.id in manifest.optional.modules:
        raise ModuleSelfDependencyError(manifest.id, optional=True)

    host = _runtime_version(host_version, "host")
    sdk = _runtime_version(sdk_version, "sdk")
    for target, current, expected in (
        ("host", host, manifest.requires.host),
        ("sdk", sdk, manifest.requires.sdk),
    ):
        if current not in SimpleSpec(expected):
            raise ModuleCompatibilityError(
                manifest.id,
                manifest.version,
                target,
                expected,
                str(current),
            )
    return manifest


def validate_manifests(
    manifests: Sequence[ModuleManifestV1],
    *,
    host_version: str,
    sdk_version: str,
    origins: Sequence[str | None] | None = None,
) -> tuple[ModuleManifestV1, ...]:
    """Validierung von Kompatibilität und Abhängigkeiten einer verfügbaren Modulmenge."""

    if origins is not None and len(origins) != len(manifests):
        raise ValueError("origins must have the same length as manifests")

    modules_by_id: dict[str, ModuleManifestV1] = {}
    first_index_by_id: dict[str, int] = {}
    for index, manifest in enumerate(manifests):
        if manifest.id in modules_by_id:
            duplicate_origins: tuple[str | None, ...] = ()
            if origins is not None:
                duplicate_origins = (origins[first_index_by_id[manifest.id]], origins[index])
            raise DuplicateModuleIdError(manifest.id, origins=duplicate_origins)
        modules_by_id[manifest.id] = manifest
        first_index_by_id[manifest.id] = index

    config_owners: dict[str, str] = {}
    schema_owners: dict[str, str] = {}
    for manifest in manifests:
        if manifest.config is not None:
            namespace = manifest.config.namespace
            if namespace in config_owners:
                raise DuplicateConfigNamespaceError(
                    namespace, (config_owners[namespace], manifest.id)
                )
            config_owners[namespace] = manifest.id
        if manifest.persistence is not None:
            schema = manifest.persistence.schema_name
            if schema in schema_owners:
                raise DuplicatePersistenceSchemaError(
                    schema, (schema_owners[schema], manifest.id)
                )
            schema_owners[schema] = manifest.id

    for manifest in manifests:
        validate_manifest(
            manifest,
            host_version=host_version,
            sdk_version=sdk_version,
        )
        for dependency_id, expected in manifest.requires.modules.items():
            if dependency_id == manifest.id:
                raise ModuleSelfDependencyError(manifest.id, optional=False)
            dependency = modules_by_id.get(dependency_id)
            if dependency is None:
                raise MissingModuleDependencyError(manifest.id, dependency_id, expected)
            if not _matches(dependency.version, expected):
                raise ModuleDependencyVersionError(
                    manifest.id,
                    dependency_id,
                    expected,
                    dependency.version,
                    optional=False,
                )
        for dependency_id, expected in manifest.optional.modules.items():
            if dependency_id == manifest.id:
                raise ModuleSelfDependencyError(manifest.id, optional=True)
            dependency = modules_by_id.get(dependency_id)
            if dependency is not None and not _matches(dependency.version, expected):
                raise ModuleDependencyVersionError(
                    manifest.id,
                    dependency_id,
                    expected,
                    dependency.version,
                    optional=True,
                )
    return tuple(manifests)


def module_manifest_json_schema() -> dict[str, Any]:
    """Liefere das deterministische JSON Schema des Manifest-V1-Single-Source-of-Truth."""

    schema = ModuleManifestV1.model_json_schema(by_alias=True)
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **schema}
