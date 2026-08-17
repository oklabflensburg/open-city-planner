import uuid

import pytest
from fastapi import HTTPException

import app.services.oauth_account_service as service
from app.models.oauth_account import UserOAuthAccount
from app.models.user import User
from app.schemas.oauth import OAuthIdentity
from app.services.oauth_account_service import (
    authenticate_oauth_identity,
    link_oauth_account,
    normalize_provider,
    unlink_oauth_account,
)


class FakeSession:
    def __init__(self) -> None:
        self.users: dict[object, User] = {}
        self.accounts: list[UserOAuthAccount] = []
        self.added: list[object] = []
        self.commits = 0

    def add(self, item: object) -> None:
        self.added.append(item)
        if isinstance(item, User):
            self.users[item.id] = item
        if isinstance(item, UserOAuthAccount):
            self.accounts.append(item)

    async def flush(self) -> None:
        for item in self.added:
            if isinstance(item, User):
                self.users[item.id] = item

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass

    async def refresh(self, _item: object) -> None:
        pass

    async def get(self, _model: object, key: object) -> User | None:
        return self.users.get(key)

    async def scalar(self, statement: object) -> object | None:
        text = str(statement).lower()
        if "count" in text:
            return len([account for account in self.accounts if account.provider != "github"])
        return None

    async def delete(self, item: object) -> None:
        if isinstance(item, UserOAuthAccount):
            self.accounts.remove(item)


def identity(provider: str = "github") -> OAuthIdentity:
    return OAuthIdentity(
        provider=provider,
        subject="subject-1",
        email="new@example.org",
        email_verified=True,
        username="kunstbube",
        display_name="Kunstbube",
        avatar_url="https://example.org/avatar.png",
    )


def test_normalize_provider() -> None:
    assert normalize_provider(" GitHub ") == "github"


@pytest.mark.asyncio
async def test_authenticate_existing_oauth_user_updates_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    user = User(
        id=uuid.uuid4(),
        email="new@example.org",
        is_active=True,
        avatar_url="/api/v1/media/avatars/local.webp",
    )
    account = UserOAuthAccount(user_id=user.id, provider="github", provider_subject="subject-1")
    session.users[user.id] = user
    monkeypatch.setattr(service, "get_by_provider_subject", async_return(account))

    result = await authenticate_oauth_identity(session, identity())

    assert result is user
    assert user.avatar_url == "/api/v1/media/avatars/local.webp"
    assert user.last_login_at is not None
    assert account.provider_username == "kunstbube"
    assert account.provider_avatar_url == "https://example.org/avatar.png"
    assert account.last_login_at is not None
    assert user.is_verified is True


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["github", "google", "mastodon"])
async def test_authenticate_existing_inactive_oauth_user_is_denied_without_duplicate(
    provider: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = FakeSession()
    user = User(id=uuid.uuid4(), email="inactive@example.org", is_active=False)
    account = UserOAuthAccount(
        user_id=user.id,
        provider=provider,
        provider_subject="subject-1",
        provider_instance="https://social.example" if provider == "mastodon" else None,
    )
    session.users[user.id] = user
    monkeypatch.setattr(service, "get_by_provider_subject", async_return(account))
    oauth_identity = identity(provider).model_copy(
        update={"provider_instance": account.provider_instance}
    )

    with pytest.raises(HTTPException) as exc_info:
        await authenticate_oauth_identity(session, oauth_identity)

    assert exc_info.value.detail["error"]["code"] == "ACCOUNT_INACTIVE"
    assert not any(isinstance(item, User) for item in session.added)
    assert session.commits == 0


@pytest.mark.asyncio
async def test_authenticate_does_not_verify_non_matching_provider_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    user = User(id=uuid.uuid4(), email="other@example.org", is_active=True, is_verified=False)
    account = UserOAuthAccount(user_id=user.id, provider="github", provider_subject="subject-1")
    session.users[user.id] = user
    monkeypatch.setattr(service, "get_by_provider_subject", async_return(account))

    await authenticate_oauth_identity(session, identity())

    assert user.is_verified is False


@pytest.mark.asyncio
async def test_authenticate_rejects_email_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession()
    monkeypatch.setattr(service, "get_by_provider_subject", async_return(None))
    monkeypatch.setattr(service, "get_user_by_email", async_return(User(email="user@example.org")))
    conflicted = OAuthIdentity(
        provider="github", subject="subject-1", email="user@example.org", email_verified=True
    )

    with pytest.raises(HTTPException) as exc:
        await authenticate_oauth_identity(session, conflicted)

    assert exc.value.status_code == 409
    assert exc.value.detail["error"]["code"] == "OAUTH_EMAIL_CONFLICT"


@pytest.mark.asyncio
async def test_link_rejects_identity_linked_to_other_user(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession()
    user = User(id=uuid.uuid4(), email="new@example.org", is_active=True)
    other = User(id=uuid.uuid4(), email="other@example.org", is_active=True)
    session.users[user.id] = user
    session.users[other.id] = other
    monkeypatch.setattr(
        service,
        "get_by_provider_subject",
        async_return(
            UserOAuthAccount(user_id=other.id, provider="github", provider_subject="subject-1")
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await link_oauth_account(session, user, identity())

    assert exc.value.status_code == 409
    assert exc.value.detail["error"]["code"] == "OAUTH_ACCOUNT_ALREADY_LINKED"


@pytest.mark.asyncio
async def test_link_verifies_matching_provider_email(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession()
    user = User(id=uuid.uuid4(), email="new@example.org", is_active=True, is_verified=False)
    monkeypatch.setattr(service, "get_by_provider_subject", async_return(None))
    monkeypatch.setattr(service, "get_for_user_provider", async_return(None))

    await link_oauth_account(session, user, identity("google"))

    assert user.is_verified is True


@pytest.mark.asyncio
async def test_link_does_not_trust_unverified_provider_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    user = User(id=uuid.uuid4(), email="new@example.org", is_active=True, is_verified=False)
    unverified = identity("google").model_copy(update={"email_verified": False})
    monkeypatch.setattr(service, "get_by_provider_subject", async_return(None))
    monkeypatch.setattr(service, "get_for_user_provider", async_return(None))

    await link_oauth_account(session, user, unverified)

    assert user.is_verified is False


@pytest.mark.asyncio
async def test_unlink_blocks_last_auth_method(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession()
    user = User(id=uuid.uuid4(), email="new@example.org", is_active=True, password_hash=None)
    session.users[user.id] = user
    monkeypatch.setattr(
        service,
        "get_for_user_provider",
        async_return(
            UserOAuthAccount(user_id=user.id, provider="github", provider_subject="subject-1")
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await unlink_oauth_account(session, user, "github")

    assert exc.value.status_code == 409
    assert exc.value.detail["error"]["code"] == "LAST_AUTH_METHOD"


def async_return(value: object):
    async def inner(*_args: object, **_kwargs: object) -> object:
        return value

    return inner
