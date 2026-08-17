from unittest.mock import AsyncMock

import pytest

from app.services import gis_mutations


@pytest.mark.asyncio
async def test_gis_mutation_versions_every_dependent_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    session = object()
    bump = AsyncMock(return_value=None)
    monkeypatch.setattr(gis_mutations, "bump_cache_versions", bump)

    await gis_mutations.invalidate_gis_after_mutation(session)  # type: ignore[arg-type]

    bump.assert_awaited_once_with(session, ("polygons", "analytics", "osm"))
