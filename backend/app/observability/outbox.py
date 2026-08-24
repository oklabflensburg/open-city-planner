import logging
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.observability.metrics import OUTBOX_OLDEST_AGE, OUTBOX_PENDING

logger = logging.getLogger(__name__)


async def update_outbox_gauges(
    session,
    model,
    *,
    outbox_type: str,
    pending_statuses: tuple[str, ...],
) -> None:
    try:
        count, oldest = (
            await session.execute(
                select(func.count(model.id), func.min(model.created_at)).where(
                    model.status.in_(pending_statuses)
                )
            )
        ).one()
    except Exception as exc:  # noqa: BLE001 - metrics must not break outbox processing
        logger.warning(
            "outbox_metrics_collection_failed",
            extra={"outbox_type": outbox_type, "error_type": type(exc).__name__},
        )
        return
    OUTBOX_PENDING.labels(outbox_type).set(int(count or 0))
    age = 0.0
    if oldest is not None:
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=UTC)
        age = max(0.0, (datetime.now(UTC) - oldest).total_seconds())
    OUTBOX_OLDEST_AGE.labels(outbox_type).set(age)
