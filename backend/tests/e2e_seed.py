"""Deterministische Host-Kerndaten für browserbasierte End-to-End-Tests."""

import asyncio
import uuid

from geoalchemy2.elements import WKTElement

from app.auth.passwords import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.user_polygon import UserPolygon

E2E_PASSWORD = "playwright-test-password"


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        session.add_all(
            [
                User(
                    id=uuid.UUID("33333333-3333-4333-8333-333333333333"),
                    email="account@example.org",
                    password_hash=hash_password(E2E_PASSWORD),
                    first_name="Account",
                    last_name="Owner",
                    display_name="Account Owner",
                    is_active=True,
                    is_verified=True,
                    roles=[],
                ),
                User(
                    id=uuid.UUID("22222222-2222-4222-8222-222222222222"),
                    email="admin@example.org",
                    password_hash=hash_password(E2E_PASSWORD),
                    first_name="Ada",
                    last_name="Admin",
                    display_name="Ada Admin",
                    is_active=True,
                    is_verified=True,
                    is_superuser=True,
                    roles=[],
                ),
                UserPolygon(
                    uuid=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
                    name="E2E-Testfläche",
                    slug="e2e-testflaeche",
                    description="Deterministische Testfläche für die Browser-Tests.",
                    address_display_name="E2E-Testfläche, Flensburg",
                    address_city="Flensburg",
                    address_lookup_status="resolved",
                    occupancy_status="UNKNOWN",
                    occupancy_source="UNKNOWN",
                    business_structure="UNKNOWN",
                    category="custom",
                    geometry=WKTElement(
                        "POLYGON((9.428 54.788,9.432 54.788,9.432 54.792,9.428 54.792,9.428 54.788))",
                        srid=4326,
                    ),
                    properties={"source": "e2e"},
                ),
            ]
        )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
