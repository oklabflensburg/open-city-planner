"""Build the hermetic passive Analysis Areas migration fixture used by required CI."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import stat
import sys
import zipfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.platform.modules.bundle import build_ocp_bundle
from app.platform.modules.installer import (
    ModuleProvenance,
    ModuleSource,
)

MODULE_ID = "analysis-areas"
MODULE_VERSION = "0.0.0"
PACKAGE_NAME = "ocp_module_analysis_areas"
DIST_INFO = f"{PACKAGE_NAME}-{MODULE_VERSION}.dist-info"
MIGRATION_ROOT = Path(__file__).parent / "module_migrations/analysis_areas_history"
ADOPTED_REVISIONS = (
    "20260814_0014",
    "20260817_0023",
    "20260818_0025",
    "20260819_0032",
)
MANIFEST: dict[str, object] = {
    "manifest_version": 1,
    "id": MODULE_ID,
    "name": "Analysis Areas passive migration fixture",
    "version": MODULE_VERSION,
    "requires": {
        "host": ">=0.2.0,<1.0.0",
        "sdk": ">=1.15.0,<2.0.0",
        "modules": {},
    },
    "optional": {"modules": {}},
    "backend": {"package": "ocp-module-analysis-areas"},
    "capabilities": [],
    "permissions": [],
    "persistence": {"schema": "analysis_areas", "migrations": True},
}
ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


def _module_source() -> str:
    return f'''"""Passive CI fixture; this is not the Analysis Areas runtime module."""

from sqlalchemy import MetaData

from app.platform.modules.sdk import (
    ModuleDefinition,
    ModuleMigrationSource,
    ModulePersistenceContribution,
    parse_manifest,
)

MANIFEST = parse_manifest({MANIFEST!r}, origin=__name__)


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
        schema="analysis_areas",
        migration_source=ModuleMigrationSource(
            package="{PACKAGE_NAME}",
            resource="migrations/history",
            revision_namespace="mod_analysis_areas",
            adopted_revisions=frozenset({ADOPTED_REVISIONS!r}),
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


def build_wheel(output: Path) -> Path:
    """Create a deterministic, installable wheel containing only passive history."""

    members: dict[str, bytes] = {
        f"{PACKAGE_NAME}/__init__.py": b"",
        f"{PACKAGE_NAME}/module.py": _module_source().encode(),
        f"{PACKAGE_NAME}/migrations/__init__.py": b"",
        f"{PACKAGE_NAME}/migrations/history/__init__.py": b"",
        f"{DIST_INFO}/METADATA": (
            f"Metadata-Version: 2.1\nName: ocp-module-analysis-areas\nVersion: {MODULE_VERSION}\n"
        ).encode(),
        f"{DIST_INFO}/WHEEL": (
            b"Wheel-Version: 1.0\n"
            b"Generator: open-city-planner-ci-fixture\n"
            b"Root-Is-Purelib: true\n"
            b"Tag: py3-none-any\n"
        ),
        f"{DIST_INFO}/entry_points.txt": (
            f"[open_city_planner.modules]\n{MODULE_ID} = {PACKAGE_NAME}.module:DEFINITION\n"
        ).encode(),
    }
    for migration in sorted(MIGRATION_ROOT.glob("*.py")):
        members[f"{PACKAGE_NAME}/migrations/history/{migration.name}"] = migration.read_bytes()

    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for name, payload in sorted(members.items()):
        writer.writerow(_record_line(name, payload))
    writer.writerow((f"{DIST_INFO}/RECORD", "", ""))
    members[f"{DIST_INFO}/RECORD"] = record.getvalue().encode()

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in sorted(members.items()):
            _write_member(archive, name, payload)
    return output


def build_bundle(output: Path, *, source_commit: str) -> str:
    wheel = output.with_name(f"{PACKAGE_NAME}-{MODULE_VERSION}-py3-none-any.whl")
    build_wheel(wheel)
    try:
        return build_ocp_bundle(
            output,
            manifest=MANIFEST,
            publisher="oklabflensburg-ci-fixture",
            source=ModuleSource(
                type="local",
                reference="backend/tests/fixtures/module_migrations/analysis_areas_history",
            ),
            provenance=ModuleProvenance(
                source_repository=("https://github.com/oklabflensburg/open-city-planner"),
                source_commit=source_commit,
                build_workflow="github-actions/required-module-migrations",
                license="AGPL-3.0-only",
            ),
            backend_artifact=wheel,
        )
    finally:
        wheel.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    digest = build_bundle(args.output, source_commit=args.source_commit)
    print(f"{args.output} sha256:{digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
