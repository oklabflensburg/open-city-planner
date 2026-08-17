import argparse
import asyncio
import json

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.services.notifications import cleanup_notifications


async def run(retention_days: int) -> None:
    async with AsyncSessionLocal() as session:
        deleted = await cleanup_notifications(session, retention_days=retention_days)
    print(json.dumps({"deleted": deleted, "retention_days": retention_days}))


def main() -> None:
    parser = argparse.ArgumentParser(description="Alte Stadtplaner-Benachrichtigungen löschen")
    parser.add_argument(
        "--retention-days", type=int, default=get_settings().notification_retention_days
    )
    args = parser.parse_args()
    asyncio.run(run(max(1, args.retention_days)))


if __name__ == "__main__":
    main()
