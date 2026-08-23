import argparse
import asyncio

from app.db.session import AsyncSessionLocal
from app.observability.jobs import observed_job
from app.services.email_outbox import process_due_email_outbox


@observed_job("email_outbox")
async def run(limit: int) -> None:
    async with AsyncSessionLocal() as session:
        result = await process_due_email_outbox(session, limit=limit)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Fällige E-Mails aus der Outbox versenden")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    asyncio.run(run(max(1, min(args.limit, 100))))


if __name__ == "__main__":
    main()
