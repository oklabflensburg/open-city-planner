import argparse
import asyncio
import logging

from app.db.base import AsyncSessionLocal
from app.services.polygon_outbox import process_due_polygon_outbox

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def async_main(limit: int) -> None:
    async with AsyncSessionLocal() as session:
        result = await process_due_polygon_outbox(session, limit=limit)
        logger.info("Polygon outbox processing complete. processed=%d failed=%d dead_letter=%d", result["processed"], result["failed"], result["dead_letter"])

def main() -> None:
    parser = argparse.ArgumentParser(description="Fällige Polygon-Ereignisse aus der Outbox verarbeiten")
    parser.add_argument("--limit", type=int, default=50, help="Maximale Anzahl zu verarbeitender Ereignisse")
    args = parser.parse_args()
    asyncio.run(async_main(args.limit))

if __name__ == "__main__":
    main()
