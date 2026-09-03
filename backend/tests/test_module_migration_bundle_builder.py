from __future__ import annotations

import zipfile
from pathlib import Path

from app.platform.modules.bundle import staged_ocp_bundle
from app.platform.modules.discovery import EntryPointModuleDiscovery
from app.platform.modules.installer import (
    ModuleProvenance,
    ModuleSource,
    installed_backend_distribution_paths,
    read_modules_lock,
)
from tests.fixtures.build_module_migration_bundle import (
    LoadedPassiveMigrationBundleFixture,
    PassiveMigrationBundleFixture,
    build_bundle,
)
from tests.test_module_installer import _installer


def neutral_fixture(migration_history: Path) -> LoadedPassiveMigrationBundleFixture:
    return LoadedPassiveMigrationBundleFixture(
        definition=PassiveMigrationBundleFixture(
            module_id="test-migration-module",
            display_name="Neutral passive migration fixture",
            module_version="0.0.0",
            python_distribution="ocp-module-test-migration-module",
            python_package="ocp_module_test_migration_module",
            persistence_schema="test_migration_module",
            revision_namespace="mod_test_migration_module",
            migration_history="neutral_history",
            adopted_revisions=("neutral_history_0001",),
            host_requirement=">=0.2.0,<1.0.0",
            sdk_requirement=">=1.15.0,<2.0.0",
            publisher="neutral-test-fixture",
            source=ModuleSource(type="local", reference="tests/fixtures/neutral_history"),
            provenance=ModuleProvenance(
                source_repository="https://github.com/example/test-migration-module",
                source_commit="a" * 40,
                build_workflow="tests/passive-migration-builder",
                license="AGPL-3.0-only",
            ),
        ),
        migration_history=migration_history,
    )


def test_generic_passive_migration_bundle_is_deterministic_and_installable(
    tmp_path: Path,
) -> None:
    migration_history = tmp_path / "neutral_history"
    migration_history.mkdir()
    migration_payload = b'''"""Arbitrary migration copied byte-for-byte."""\n\nrevision = "neutral_history_0001"\ndown_revision = None\nbranch_labels = None\ndepends_on = None\n'''
    (migration_history / "neutral_history_0001.py").write_bytes(migration_payload)
    fixture = neutral_fixture(migration_history)
    first = tmp_path / "first.ocp"
    second = tmp_path / "second.ocp"

    assert build_bundle(first, fixture) == build_bundle(second, fixture)
    assert first.read_bytes() == second.read_bytes()
    assert not list(tmp_path.glob("ocp-migration-fixture-*"))
    assert not list(tmp_path.glob("*.whl"))

    with staged_ocp_bundle(first) as (package_root, package):
        assert package.module_id == "test-migration-module"
        assert package.version == "0.0.0"
        assert package.frontend is None
        assert package.backend is not None
        wheel = package_root / package.backend.path
        with zipfile.ZipFile(wheel) as archive:
            entry_points = archive.read(
                "ocp_module_test_migration_module-0.0.0.dist-info/entry_points.txt"
            ).decode()
            module_source = archive.read("ocp_module_test_migration_module/module.py").decode()
            copied_migration = archive.read(
                "ocp_module_test_migration_module/migrations/history/neutral_history_0001.py"
            )
        assert (
            "test-migration-module = ocp_module_test_migration_module.module:DEFINITION"
        ) in entry_points
        assert "ModulePersistenceContribution" in module_source
        assert "def register(self, context)" in module_source
        assert copied_migration == migration_payload

        installer = _installer(tmp_path / "modules")
        installed = installer.install(package_root)

    assert installed.enabled is False
    assert read_modules_lock(installer.lock_path).modules == (installed,)
    distribution_path = installed_backend_distribution_paths(installer.root)[0]
    definitions = EntryPointModuleDiscovery(
        distribution_paths=(distribution_path,)
    ).discover_available()
    assert len(definitions) == 1
    definition = definitions[0]
    assert definition.declared_id == "test-migration-module"
    assert definition.persistence is not None
    assert definition.persistence.schema == "test_migration_module"
    assert definition.persistence.metadata.tables == {}
    assert definition.persistence.migration_source is not None
    assert definition.persistence.migration_source.package == "ocp_module_test_migration_module"
    assert definition.persistence.migration_source.resource == "migrations/history"
    assert definition.persistence.migration_source.revision_namespace == "mod_test_migration_module"
    assert definition.persistence.migration_source.adopted_revisions == frozenset(
        {"neutral_history_0001"}
    )


def test_generic_builder_has_no_domain_module_dependency() -> None:
    builder = Path(__file__).parent / "fixtures/build_module_migration_bundle.py"
    source = builder.read_text(encoding="utf-8").casefold()

    assert "analysis-areas" not in source
    assert "analysis_areas" not in source
    assert "mod_analysis_areas" not in source
    assert "ocp_module_analysis_areas" not in source
