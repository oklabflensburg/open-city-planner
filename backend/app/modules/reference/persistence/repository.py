"""SQLAlchemy-Adapter hinter dem Application-Port des Referenzmoduls."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.models import ReferenceItem
from .models import ReferenceItemRecord


class SqlAlchemyReferenceItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self, *, limit: int) -> tuple[ReferenceItem, ...]:
        records = (
            await self._session.scalars(
                select(ReferenceItemRecord)
                .order_by(ReferenceItemRecord.created_at, ReferenceItemRecord.id)
                .limit(limit)
            )
        ).all()
        return tuple(self._to_domain(record) for record in records)

    async def count(self) -> int:
        value = await self._session.scalar(select(func.count(ReferenceItemRecord.id)))
        return int(value or 0)

    def add(self, item: ReferenceItem) -> None:
        self._session.add(
            ReferenceItemRecord(
                id=item.id,
                title=item.title,
                description=item.description,
                longitude=item.longitude,
                latitude=item.latitude,
                created_at=item.created_at,
            )
        )

    @staticmethod
    def _to_domain(record: ReferenceItemRecord) -> ReferenceItem:
        return ReferenceItem(
            id=record.id,
            title=record.title,
            description=record.description,
            longitude=record.longitude,
            latitude=record.latitude,
            created_at=record.created_at,
        )
