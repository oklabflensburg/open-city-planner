"""Bewusst kleines, ausschließlich in Tests aktiviertes Runtime-Modul."""

from fastapi import APIRouter
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
        "id": "test-example-module",
        "name": "Runtime-Testmodul",
        "version": "1.0.0",
        "requires": {"host": ">=0.2.0,<1.0.0", "sdk": ">=1.0.0,<2.0.0"},
        "capabilities": ["test.ping"],
        "persistence": {"schema": "test_example_module", "migrations": False},
    },
    origin="tests.fixtures.example_backend_module",
)

METADATA = MetaData()
Table(
    "items",
    METADATA,
    Column("id", Integer, primary_key=True),
    Column("name", String(80), nullable=False),
    schema="test_example_module",
)


class ExampleBackendModule:
    manifest: ModuleManifestV1 = MANIFEST

    def register(self, context: ModuleContext) -> None:
        router = APIRouter()

        @router.get("/ping")
        async def ping() -> dict[str, str]:
            return {"status": "ok"}

        context.api.include_router(
            router,
            prefix="/api/v1/module-test",
            tags=("Module test",),
        )


DEFINITION = ModuleDefinition(
    manifest=MANIFEST,
    loader=ExampleBackendModule,
    origin="tests.fixtures.example_backend_module",
    declared_id=MANIFEST.id,
    persistence=ModulePersistenceContribution(
        module_id=MANIFEST.id,
        metadata=METADATA,
        schema="test_example_module",
    ),
)
