from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_polygon import UserPolygon
from app.schemas.analytics import (
    AnalyticsFastFacts,
    AnalyticsOverview,
    IndustryCount,
    PrimeRentData,
)
from app.services.city_metrics import get_public_city_metrics

# A shop is currently a public polygon assigned to one of the maintained retail/service
# categories. "otherAreas" and unknown/custom categories are deliberately excluded.
SHOP_CATEGORIES = (
    "warehouse",
    "fashion",
    "food",
    "electronics",
    "furniture",
    "garden",
    "other",
    "gastronomy",
    "services",
)


def _base_filters(floors: Sequence[str], area_sizes: Sequence[str]) -> list[object]:
    filters: list[object] = []
    if floors:
        filters.append(func.coalesce(UserPolygon.floor, "EG").in_(floors))
    if area_sizes:
        filters.append(
            func.coalesce(UserPolygon.properties["size"].as_string(), "M").in_(area_sizes)
        )
    return filters


async def _counts(
    session: AsyncSession,
    filters: Sequence[object],
) -> list[IndustryCount]:
    statement = (
        select(UserPolygon.category, func.count(UserPolygon.id))
        .where(*filters)
        .group_by(UserPolygon.category)
        .order_by(UserPolygon.category)
    )
    rows = (await session.execute(statement)).all()
    return [IndustryCount(category=category, count=int(count)) for category, count in rows]


async def analytics_overview(
    session: AsyncSession,
    *,
    categories: Sequence[str] = (),
    floors: Sequence[str] = (),
    area_sizes: Sequence[str] = (),
) -> AnalyticsOverview:
    base_filters = _base_filters(floors, area_sizes)
    category_counts = await _counts(session, base_filters)

    selected_filters = list(base_filters)
    if categories:
        selected_filters.append(UserPolygon.category.in_(categories))
    distribution = await _counts(session, selected_filters)

    shops = sum(
        item.count for item in distribution if item.category in SHOP_CATEGORIES
    )
    city_metrics = await get_public_city_metrics(session)

    return AnalyticsOverview(
        fast_facts=AnalyticsFastFacts(shops=shops, **city_metrics.model_dump()),
        industry_distribution=distribution,
        category_counts=category_counts,
        # price_per_sqm is an internal management field, not a public rent dataset.
        prime_rents=PrimeRentData(),
    )
