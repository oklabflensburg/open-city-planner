from pathlib import Path
from types import SimpleNamespace

import pytest

from app.platform.modules.errors import (
    DuplicatePermissionError,
    InvalidPermissionNamespaceError,
    PermissionRegistrySealedError,
)
from app.platform.modules.manifest import parse_manifest
from app.platform.modules.permissions import (
    LegacyRolePermissionResolver,
    PermissionEngine,
    PermissionRegistry,
    RegistryPermissionPort,
)
from app.platform.modules.sdk import PermissionDefinition


def permission(
    permission_id: str, module_id: str = "example-module"
) -> PermissionDefinition:
    return PermissionDefinition(
        id=permission_id,
        module_id=module_id,
        description=f"Test permission {permission_id}",
    )


def subject(*, superuser: bool = False, roles: list[str] | None = None):
    return SimpleNamespace(is_superuser=superuser, roles=roles or [])


def test_registry_registers_and_sorts_multiple_permissions() -> None:
    registry = PermissionRegistry()
    registry.register(permission("example-module.use"))
    registry.register(permission("example-module.admin"))

    assert registry.permission_ids == (
        "example-module.admin",
        "example-module.use",
    )
    assert registry.get("example-module.use") is not None


def test_duplicate_reports_both_provider_modules() -> None:
    registry = PermissionRegistry()
    registry.register(permission("example-module.use"))

    with pytest.raises(DuplicatePermissionError) as error:
        registry.register(permission("example-module.use", module_id="other-module"))

    assert error.value.permission_id == "example-module.use"
    assert error.value.provider_module == "example-module"
    assert error.value.conflicting_module == "other-module"


@pytest.mark.parametrize(
    "definition",
    [
        permission("other-module.use"),
        permission("platform.superuser"),
        permission("Example-module.use"),
        permission("platform.superuser", module_id="platform"),
    ],
)
def test_namespace_and_platform_reservation_are_enforced(
    definition: PermissionDefinition,
) -> None:
    with pytest.raises(InvalidPermissionNamespaceError):
        PermissionRegistry().register(definition)


def test_host_can_register_platform_permission_and_seal_registry() -> None:
    registry = PermissionRegistry()
    registry.register_platform(permission("platform.superuser", module_id="platform"))
    registry.seal()

    assert registry.permission_ids == ("platform.superuser",)
    with pytest.raises(PermissionRegistrySealedError):
        registry.register_platform(permission("platform.verwaltung", module_id="platform"))


def test_only_active_manifest_permissions_are_registered() -> None:
    active = parse_manifest(
        {
            "manifest_version": 1,
            "id": "example-module",
            "name": "Example",
            "version": "1.0.0",
            "requires": {"host": ">=1.0.0,<2.0.0", "sdk": ">=1.0.0,<2.0.0"},
            "permissions": ["example-module.use", "example-module.admin"],
        }
    )
    registry = PermissionRegistry()
    registry.register_manifest(active)

    assert registry.permission_ids == (
        "example-module.admin",
        "example-module.use",
    )
    assert registry.get("disabled-module.use") is None


def test_evaluation_is_default_deny_and_preserves_legacy_roles() -> None:
    registry = PermissionRegistry()
    registry.register_platform(permission("platform.verwaltung", module_id="platform"))
    registry.register(permission("social.publish", module_id="social"))
    registry.seal()
    engine = PermissionEngine(
        registry,
        LegacyRolePermissionResolver({"VERWALTUNG": ("platform.verwaltung",)}),
    )

    assert engine.allows(subject(roles=["verwaltung"]), "platform.verwaltung") is True
    assert engine.allows(subject(roles=["VERWALTUNG"]), "social.publish") is False
    assert engine.allows(subject(superuser=True), "social.publish") is True
    assert engine.allows(subject(superuser=True), "unknown.permission") is False
    assert engine.snapshot(subject(roles=["VERWALTUNG"])) == ("platform.verwaltung",)
    assert engine.snapshot(subject(superuser=True)) == (
        "platform.verwaltung",
        "social.publish",
    )


@pytest.mark.asyncio
async def test_public_permission_port_loads_identity_server_side() -> None:
    registry = PermissionRegistry()
    registry.register(permission("example-module.use"))
    registry.seal()
    engine = PermissionEngine(registry)

    async def load_subject(principal_id: str):
        return subject(superuser=principal_id == "known")

    port = RegistryPermissionPort(engine, load_subject)
    assert await port.is_allowed("example-module.use", principal_id="known") is True
    assert await port.is_allowed("example-module.use", principal_id=None) is False


def test_generic_host_registry_contains_no_fach_permission_catalog() -> None:
    source = (Path(__file__).parents[1] / "app/platform/modules/permissions.py").read_text()
    assert "social.publish" not in source
    assert "statistics.import" not in source
    assert "polygons.manage" not in source
