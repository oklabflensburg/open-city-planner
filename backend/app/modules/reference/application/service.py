"""Use Cases des Referenzmoduls; alle Host-Dienste kommen über SDK-Ports."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.platform.modules.sdk import ModuleContext

from ..domain.events import ReferenceItemCreated
from ..domain.models import ReferenceItem
from ..persistence.repository import SqlAlchemyReferenceItemRepository
from ..settings import ReferenceSettings


@dataclass(frozen=True, slots=True)
class CreateReferenceItem:
    title: str
    description: str
    longitude: float
    latitude: float


class ReferencePermissionDenied(Exception):
    """Der Host hat die modulspezifische Schreibberechtigung abgelehnt."""


class ReferenceItemService:
    def __init__(self, context: ModuleContext) -> None:
        if context.database is None:
            raise RuntimeError("The reference module requires the database port.")
        self._context = context
        self._database = context.database
        self._settings = (
            context.settings.require(ReferenceSettings)
            if context.settings is not None
            else ReferenceSettings()
        )

    async def list_items(self) -> tuple[ReferenceItem, ...]:
        async with self._database.session() as session:
            return await SqlAlchemyReferenceItemRepository(session).list(
                limit=self._settings.max_items
            )

    async def count_items(self) -> int:
        async with self._database.session() as session:
            return await SqlAlchemyReferenceItemRepository(session).count()

    async def create_item(
        self,
        command: CreateReferenceItem,
        *,
        principal_id: str | None,
    ) -> ReferenceItem:
        if self._context.permissions is None or not await self._context.permissions.is_allowed(
            "reference.items-write", principal_id=principal_id
        ):
            raise ReferencePermissionDenied
        item = ReferenceItem(
            id=str(uuid4()),
            title=command.title,
            description=command.description,
            longitude=command.longitude,
            latitude=command.latitude,
            created_at=datetime.now(UTC),
        )
        async with self._database.session() as session:
            SqlAlchemyReferenceItemRepository(session).add(item)
            if self._context.events is not None:
                await self._context.events.publish_after_commit(
                    ReferenceItemCreated(item_id=item.id, title=item.title),
                    session=session,
                )
        return item
