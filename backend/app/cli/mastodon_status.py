import asyncio
import json

from app.core.config import get_settings
from app.integrations.mastodon import MastodonClient, MastodonError


async def run() -> None:
    settings = get_settings()
    result: dict[str, object] = {
        "enabled": settings.mastodon_enabled,
        "configured": bool(settings.mastodon_access_token),
        "account": settings.mastodon_account_handle,
        "reachable": None,
    }
    if settings.mastodon_access_token:
        client = MastodonClient(settings.mastodon_base_url, settings.mastodon_access_token, timeout=settings.mastodon_timeout_seconds)
        try:
            credentials = await client.verify_credentials()
            result.update(reachable=True, verified_account=credentials.get("acct"))
        except MastodonError as exc:
            result.update(reachable=False, error=f"HTTP {exc.status_code}" if exc.status_code else "network")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(run())
