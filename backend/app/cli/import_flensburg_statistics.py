import argparse
import asyncio
import json

from app.db.session import AsyncSessionLocal
from app.observability.jobs import observed_job
from app.services.flensburg_statistics_import import import_flensburg_statistics
from app.services.flensburg_superset import FlensburgSupersetClient


@observed_job("flensburg_statistics_sync")
async def run(discover_only: bool) -> None:
    client = FlensburgSupersetClient()
    if discover_only:
        dashboard, charts, datasets = await asyncio.gather(
            client.dashboard(), client.charts(), client.datasets()
        )
        print(json.dumps({
            "dashboard": {
                "id": dashboard.get("id"),
                "title": dashboard.get("dashboard_title"),
                "changed_on": dashboard.get("changed_on"),
            },
            "charts": [
                {"id": chart["id"], "title": chart["slice_name"],
                 "dataset": chart.get("form_data", {}).get("datasource")}
                for chart in charts
            ],
            "datasets": [
                {"id": dataset["id"], "name": dataset["datasource_name"],
                 "columns": [column["column_name"] for column in dataset["columns"]]}
                for dataset in datasets
            ],
        }, ensure_ascii=False, indent=2))
        return
    async with AsyncSessionLocal() as session:
        report = await import_flensburg_statistics(session, client)
        print(json.dumps(report.__dict__, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Öffentliche Statistik aus dem Flensburger Zahlenspiegel importieren"
    )
    parser.add_argument("--discover-only", action="store_true")
    arguments = parser.parse_args()
    asyncio.run(run(arguments.discover_only))


if __name__ == "__main__":
    main()
