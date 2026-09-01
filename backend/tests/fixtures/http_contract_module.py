"""External-style consumer fixture for the public module HTTP contract."""

from app.platform.modules.sdk import (
    HttpResponsePort,
    ModuleContext,
    ModuleDefinition,
    ModuleManifestV1,
    parse_manifest,
)

MANIFEST = parse_manifest(
    {
        "manifest_version": 1,
        "id": "test-http-consumer",
        "name": "HTTP Contract Consumer",
        "version": "1.0.0",
        "requires": {"host": ">=0.2.0,<1.0.0", "sdk": ">=1.12.0,<2.0.0"},
        "capabilities": [],
        "permissions": [],
    },
    origin="tests.fixtures.http_contract_module",
)


class HttpContractConsumerModule:
    manifest: ModuleManifestV1 = MANIFEST

    def register(self, context: ModuleContext) -> None:
        del context


async def fetch_provider_document(
    context: ModuleContext,
    *,
    path: str = "/document",
) -> HttpResponsePort:
    if context.http is None:
        raise RuntimeError("The Host does not provide the public HTTP client port.")
    async with context.http.create(
        service_name="wikidata",
        base_url="https://provider.example",
    ) as client:
        return await client.request("GET", path, params={"format": "json"})


DEFINITION = ModuleDefinition(
    manifest=MANIFEST,
    loader=HttpContractConsumerModule,
    origin="tests.fixtures.http_contract_module",
    declared_id=MANIFEST.id,
)
