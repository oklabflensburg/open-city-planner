import argparse
import asyncio

from app.db.session import AsyncSessionLocal
from app.observability.jobs import observed_job
from app.services.polygon_outbox import process_due_polygon_outbox


@observed_job("polygon_outbox")
async def async_main(limit: int) -> None:
    async with AsyncSessionLocal() as session:
        result = await process_due_polygon_outbox(session, limit=limit)
        return result

def main() -> None:
    parser = argparse.ArgumentParser(description="Fällige Polygon-Ereignisse aus der Outbox verarbeiten")
    parser.add_argument("--limit", type=int, default=50, help="Maximale Anzahl zu verarbeitender Ereignisse")
    args = parser.parse_args()
    asyncio.run(async_main(args.limit))

if __name__ == "__main__":
    main()
