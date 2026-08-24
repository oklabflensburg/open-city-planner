import argparse
import asyncio

from app.db.session import AsyncSessionLocal
from app.observability.jobs import observed_job
from app.services.social_publishing import publish_due_events


@observed_job("social_publisher")
async def run(limit: int) -> None:
    async with AsyncSessionLocal() as session:
        result = await publish_due_events(session, limit=limit)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Fällige Mastodon-Outbox-Ereignisse veröffentlichen")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    asyncio.run(run(max(1, min(args.limit, 100))))


if __name__ == "__main__":
    main()
