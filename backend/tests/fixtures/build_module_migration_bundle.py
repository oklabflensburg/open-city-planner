"""Build deterministic passive migration-only module bundles from typed fixtures."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.platform.modules.bundle import build_ocp_bundle
from app.platform.modules.installer import ModuleProvenance, ModuleSource
from app.platform.modules.manifest import ModuleId, SemanticVersion, SemanticVersionRange

ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
PYTHON_IMPORT_PATTERN = r"^[a-z][a-z0-9_]*$"
PYTHON_DISTRIBUTION_PATTERN = r"^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$"
POSTGRES_IDENTIFIER_PATTERN = r"^[a-z][a-z0-9_]*$"
REVISION_PATTERN = r"^[a-zA-Z0-9_]+$"


class PassiveMigrationBundleFixture(BaseModel):
    """Strict, module-neutral input for one passive migration fixture bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    module_id: ModuleId
    display_name: str = Field(min_length=1, max_length=255)
    module_version: SemanticVersion
    python_distribution: str = Field(pattern=PYTHON_DISTRIBUTION_PATTERN)
    python_package: str = Field(pattern=PYTHON_IMPORT_PATTERN)
    persistence_schema: str = Field(pattern=POSTGRES_IDENTIFIER_PATTERN)
    revision_namespace: str = Field(pattern=POSTGRES_IDENTIFIER_PATTERN)
    migration_history: str = Field(min_length=1, max_length=512)
    adopted_revisions: tuple[str, ...] = Field(min_length=1)
    host_requirement: SemanticVersionRange
    sdk_requirement: SemanticVersionRange
    publisher: str = Field(min_length=1, max_length=255)
    source: ModuleSource
    provenance: ModuleProvenance

    @field_validator("migration_history")
    @classmethod
    def migration_history_is_portable(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            "\x00" in value
            or "\\" in value
            or path.is_absolute()
            or ".." in path.parts
            or value != path.as_posix()
        ):
            raise ValueError("migration_history must be portable and relative to its fixture")
        return value

    @field_validator("adopted_revisions")
    @classmethod
    def revisions_are_unique_identifiers(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("adopted_revisions must be unique")
        invalid = next(
            (revision for revision in value if not re.fullmatch(REVISION_PATTERN, revision)), None
        )
        if invalid is not None:
            raise ValueError(f"invalid adopted revision {invalid!r}")
        return value

    @model_validator(mode="after")
    def wheel_identity_matches_installer_contract(self) -> PassiveMigrationBundleFixture:
        expected_package = f"ocp_module_{self.module_id.replace('-', '_')}"
        normalized_distribution = re.sub(r"[-_.]+", "_", self.python_distribution)
        if self.python_package != expected_package:
            raise ValueError(
                f"python_package must be the canonical installer namespace {expected_package!r}"
            )
        if normalized_distribution != expected_package:
            raise ValueError(
                "python_distribution must normalize to the canonical installer namespace "
                f"{expected_package!r}"
            )
        return self

    def manifest(self) -> dict[str, object]:
        return {
            "manifest_version": 1,
            "id": self.module_id,
            "name": self.display_name,
            "version": self.module_version,
            "requires": {
                "host": self.host_requirement,
                "sdk": self.sdk_requirement,
                "modules": {},
            },
            "optional": {"modules": {}},
            "backend": {"package": self.python_distribution},
            "capabilities": [],
            "permissions": [],
            "persistence": {"schema": self.persistence_schema, "migrations": True},
        }


class LoadedPassiveMigrationBundleFixture(BaseModel):
    """Validated fixture plus its safely resolved migration directory."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    definition: PassiveMigrationBundleFixture
    migration_history: Path


def load_fixture(path: Path) -> LoadedPassiveMigrationBundleFixture:
    """Load strict JSON and resolve its migration history relative to the definition."""

    definition = PassiveMigrationBundleFixture.model_validate_json(path.read_text(encoding="utf-8"))
    migration_history = path.parent.joinpath(*PurePosixPath(definition.migration_history).parts)
    if not migration_history.is_dir():
        raise ValueError(f"migration history directory does not exist: {migration_history}")
    if not any(path.name != "__init__.py" for path in migration_history.glob("*.py")):
        raise ValueError(
            f"migration history directory contains no Python revisions: {migration_history}"
        )
    return LoadedPassiveMigrationBundleFixture(
        definition=definition,
        migration_history=migration_history,
    )


def _module_source(fixture: PassiveMigrationBundleFixture) -> str:
    manifest = fixture.manifest()
    return f'''"""Passive migration test fixture; this is not a runtime module."""

from sqlalchemy import MetaData

from app.platform.modules.sdk import (
    ModuleDefinition,
    ModuleMigrationSource,
    ModulePersistenceContribution,
    parse_manifest,
)

MANIFEST = parse_manifest({manifest!r}, origin=__name__)


class PassiveMigrationFixture:
    manifest = MANIFEST

    def register(self, context):
        del context


DEFINITION = ModuleDefinition(
    manifest=MANIFEST,
    loader=PassiveMigrationFixture,
    origin=__name__,
    declared_id=MANIFEST.id,
    persistence=ModulePersistenceContribution(
        module_id=MANIFEST.id,
        metadata=MetaData(),
        schema={fixture.persistence_schema!r},
        migration_source=ModuleMigrationSource(
            package={fixture.python_package!r},
            resource="migrations/history",
            revision_namespace={fixture.revision_namespace!r},
            adopted_revisions=frozenset({fixture.adopted_revisions!r}),
        ),
    ),
)
'''


def _record_line(path: str, payload: bytes) -> tuple[str, str, str]:
    digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=")
    return path, f"sha256={digest.decode('ascii')}", str(len(payload))


def _write_member(archive: zipfile.ZipFile, name: str, payload: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    archive.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED)


def build_wheel(
    output: Path,
    fixture: LoadedPassiveMigrationBundleFixture,
) -> Path:
    """Create an installable deterministic wheel containing only passive history."""

    definition = fixture.definition
    dist_info = f"{definition.python_package}-{definition.module_version}.dist-info"
    members: dict[str, bytes] = {
        f"{definition.python_package}/__init__.py": b"",
        f"{definition.python_package}/module.py": _module_source(definition).encode(),
        f"{definition.python_package}/migrations/__init__.py": b"",
        f"{definition.python_package}/migrations/history/__init__.py": b"",
        f"{dist_info}/METADATA": (
            "Metadata-Version: 2.1\n"
            f"Name: {definition.python_distribution}\n"
            f"Version: {definition.module_version}\n"
        ).encode(),
        f"{dist_info}/WHEEL": (
            b"Wheel-Version: 1.0\n"
            b"Generator: open-city-planner-passive-migration-fixture\n"
            b"Root-Is-Purelib: true\n"
            b"Tag: py3-none-any\n"
        ),
        f"{dist_info}/entry_points.txt": (
            "[open_city_planner.modules]\n"
            f"{definition.module_id} = {definition.python_package}.module:DEFINITION\n"
        ).encode(),
    }
    for migration in sorted(fixture.migration_history.glob("*.py")):
        if migration.name == "__init__.py":
            continue
        members[f"{definition.python_package}/migrations/history/{migration.name}"] = (
            migration.read_bytes()
        )

    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for name, payload in sorted(members.items()):
        writer.writerow(_record_line(name, payload))
    writer.writerow((f"{dist_info}/RECORD", "", ""))
    members[f"{dist_info}/RECORD"] = record.getvalue().encode()

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in sorted(members.items()):
            _write_member(archive, name, payload)
    return output


def build_bundle(
    output: Path,
    fixture: LoadedPassiveMigrationBundleFixture,
    *,
    source_commit: str | None = None,
) -> str:
    """Build one passive fixture with the production OCP bundle API."""

    definition = fixture.definition
    provenance = (
        definition.provenance
        if source_commit is None
        else ModuleProvenance.model_validate(
            {**definition.provenance.model_dump(), "source_commit": source_commit}
        )
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="ocp-migration-fixture-", dir=output.parent) as temporary:
        wheel = Path(temporary) / (
            f"{definition.python_package}-{definition.module_version}-py3-none-any.whl"
        )
        build_wheel(wheel, fixture)
        return build_ocp_bundle(
            output,
            manifest=definition.manifest(),
            publisher=definition.publisher,
            source=definition.source,
            provenance=provenance,
            backend_artifact=wheel,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    fixture = load_fixture(args.fixture)
    digest = build_bundle(args.output, fixture, source_commit=args.source_commit)
    print(f"{args.output} sha256:{digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
