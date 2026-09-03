from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from app.cli import module_migrations
from app.platform.modules.bundle import staged_ocp_bundle
from app.platform.modules.installer import installed_backend_distribution_paths
from tests.fixtures.build_module_migration_bundle import build_bundle, load_fixture
from tests.test_module_installer import _installer

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DEFINITION = BACKEND_ROOT / "tests/fixtures/module_migrations/analysis_areas.json"
EXPECTED_HISTORY = {
    "20260814_0014_analysis_areas.py": (
        "f1d6bcbb61bca91a809e7ea18a0b8189cc3ee64cd2c198e14215874af81a2e48",
        "20260814_0014",
        "20260814_0013",
    ),
    "20260817_0023_area_wikidata.py": (
        "be737c5a18118585ec78265159721c2e5d975e8af511e21d49eb47ac1ec62c9d",
        "20260817_0023",
        "20260817_0022",
    ),
    "20260818_0025_osm_external_links.py": (
        "5951d0b434cc44f270e9d40e37d3fd33531ea2cd42327bddc29f5dde865ecb47",
        "20260818_0025",
        "20260818_0024",
    ),
    "20260819_0032_optimize_area_poi_analytics.py": (
        "69cabe2bc1b681ffc8a1009bdd1999ec232a82485a3670d1fb54c5e353fbbe08",
        "20260819_0032",
        "20260819_0031",
    ),
}


def _revision_edge(path: Path) -> tuple[str, str]:
    values: dict[str, str] = {}
    for statement in ast.parse(path.read_text(encoding="utf-8")).body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
            value = ast.literal_eval(statement.value)
            if isinstance(value, str):
                values[target.id] = value
    return values["revision"], values["down_revision"]


def test_analysis_areas_fixture_preserves_published_history_bytes_and_edges() -> None:
    fixture = load_fixture(FIXTURE_DEFINITION)
    definition = fixture.definition

    assert definition.module_id == "analysis-areas"
    assert definition.module_version == "0.0.0"
    assert definition.python_package == "ocp_module_analysis_areas"
    assert definition.persistence_schema == "analysis_areas"
    assert definition.revision_namespace == "mod_analysis_areas"
    assert definition.adopted_revisions == (
        "20260814_0014",
        "20260817_0023",
        "20260818_0025",
        "20260819_0032",
    )
    assert {path.name for path in fixture.migration_history.glob("*.py")} == set(EXPECTED_HISTORY)
    for filename, (expected_digest, revision, down_revision) in EXPECTED_HISTORY.items():
        path = fixture.migration_history / filename
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_digest
        assert _revision_edge(path) == (revision, down_revision)


def test_disabled_analysis_areas_fixture_is_passively_discovered_in_full_graph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = load_fixture(FIXTURE_DEFINITION)
    bundle = tmp_path / "migration-regression.ocp"
    build_bundle(bundle, fixture, source_commit="b" * 40)
    installer = _installer(tmp_path / "modules")
    with staged_ocp_bundle(bundle) as (package_root, _package):
        installed = installer.install(package_root)

    assert installed.enabled is False
    assert installed_backend_distribution_paths(installer.root)
    monkeypatch.chdir(BACKEND_ROOT)
    plan = module_migrations.run(
        "preflight",
        install_root=installer.root,
        enabled_module_ids=(),
    )
    assert plan is not None
    assert [
        (step.module_id, step.revision)
        for step in plan
        if step.revision in fixture.definition.adopted_revisions
    ] == [
        ("analysis-areas", "20260814_0014"),
        ("analysis-areas", "20260817_0023"),
        ("analysis-areas", "20260818_0025"),
        ("analysis-areas", "20260819_0032"),
    ]
    assert plan[-1].revision == "mod_reference_20260901_0002"
