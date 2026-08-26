from collections.abc import Sequence

from tests.fixtures.service_modules.analysis_areas.contracts import AnalysisAreaSummary


class InMemoryAnalysisAreaQueryService:
    async def list_areas(self) -> Sequence[AnalysisAreaSummary]:
        return (
            AnalysisAreaSummary(
                area_id="flensburg",
                name="Flensburg",
                geometry={"type": "Point", "coordinates": [9.43, 54.79]},
            ),
        )
