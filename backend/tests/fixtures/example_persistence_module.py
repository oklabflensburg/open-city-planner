"""Zweites passives Persistence-Fixture mit deklarierter Modulabhängigkeit."""

from sqlalchemy import Column, Integer, MetaData, String, Table

from app.platform.modules.sdk import (
    ModuleContext,
    ModuleDefinition,
    ModuleManifestV1,
    ModulePersistenceContribution,
    parse_manifest,
)

MANIFEST = parse_manifest(
    {
        "manifest_version": 1,
        "id": "test-persistence-dependent",
        "name": "Abhängiges Persistence-Testmodul",
        "version": "1.0.0",
        "requires": {
            "host": ">=0.2.0,<1.0.0",
            "sdk": ">=1.0.0,<2.0.0",
            "modules": {"test-example-module": ">=1.0.0,<2.0.0"},
        },
        "persistence": {
            "schema": "test_persistence_dependent",
            "migrations": False,
        },
    },
    origin="tests.fixtures.example_persistence_module",
)

METADATA = MetaData()
Table(
    "items",
    METADATA,
    Column("id", Integer, primary_key=True),
    Column("description", String(120), nullable=False),
    schema="test_persistence_dependent",
)


class ExamplePersistenceModule:
    manifest: ModuleManifestV1 = MANIFEST

    def register(self, context: ModuleContext) -> None:
        del context


DEFINITION = ModuleDefinition(
    manifest=MANIFEST,
    loader=ExamplePersistenceModule,
    origin="tests.fixtures.example_persistence_module",
    declared_id=MANIFEST.id,
    persistence=ModulePersistenceContribution(
        module_id=MANIFEST.id,
        metadata=METADATA,
        schema="test_persistence_dependent",
    ),
)
