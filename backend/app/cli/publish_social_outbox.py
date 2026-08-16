import argparse
import asyncio
import json

from app.db.session import AsyncSessionLocal
from app.services.social_publishing import publish_due_events


async def run(limit: int) -> None:
    async with AsyncSessionLocal() as session:
        result = await publish_due_events(session, limit=limit)
    print(json.dumps(result, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Fällige Mastodon-Outbox-Ereignisse veröffentlichen")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    asyncio.run(run(max(1, min(args.limit, 100))))


if __name__ == "__main__":
    main()
