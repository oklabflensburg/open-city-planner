"""Host-owned registry and policy evaluation for stable module permission IDs."""

import logging
import re
from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import Protocol

from app.platform.modules.errors import (
    DuplicatePermissionError,
    InvalidPermissionNamespaceError,
    PermissionRegistrySealedError,
)
from app.platform.modules.manifest import ModuleManifestV1
from app.platform.modules.sdk import PermissionDefinition

logger = logging.getLogger(__name__)
PERMISSION_ID_PATTERN = re.compile(
    r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*)+$"
)


class PermissionSubject(Protocol):
    is_superuser: bool
    roles: list[str] | None


class PermissionRegistry:
    """Collects active definitions deterministically and becomes immutable at bootstrap."""

    def __init__(self) -> None:
        self._definitions: dict[str, PermissionDefinition] = {}
        self._sealed = False

    @property
    def sealed(self) -> bool:
        return self._sealed

    @property
    def definitions(self) -> tuple[PermissionDefinition, ...]:
        return tuple(self._definitions[key] for key in sorted(self._definitions))

    @property
    def permission_ids(self) -> tuple[str, ...]:
        return tuple(definition.id for definition in self.definitions)

    def get(self, permission_id: str) -> PermissionDefinition | None:
        return self._definitions.get(permission_id)

    def register(self, definition: PermissionDefinition) -> None:
        if self._sealed:
            raise PermissionRegistrySealedError("The permission registry is sealed.")
        existing = self._definitions.get(definition.id)
        if existing is not None:
            raise DuplicatePermissionError(
                definition.id,
                provider_module=existing.module_id,
                conflicting_module=definition.module_id,
            )
        self._validate_ownership(definition.id, definition.module_id, platform=False)
        self._definitions[definition.id] = definition

    def register_platform(self, definition: PermissionDefinition) -> None:
        if self._sealed:
            raise PermissionRegistrySealedError("The permission registry is sealed.")
        existing = self._definitions.get(definition.id)
        if existing is not None:
            raise DuplicatePermissionError(
                definition.id,
                provider_module=existing.module_id,
                conflicting_module=definition.module_id,
            )
        self._validate_ownership(definition.id, definition.module_id, platform=True)
        self._definitions[definition.id] = definition

    def register_manifest(self, manifest: ModuleManifestV1) -> None:
        for permission_id in sorted(manifest.permissions):
            self.register(
                PermissionDefinition(
                    id=permission_id,
                    module_id=manifest.id,
                    description=permission_id,
                )
            )

    def seal(self) -> None:
        self._sealed = True

    @staticmethod
    def _validate_ownership(
        permission_id: str, module_id: str, *, platform: bool
    ) -> None:
        if not PERMISSION_ID_PATTERN.fullmatch(permission_id):
            raise InvalidPermissionNamespaceError(permission_id, module_id=module_id)
        if platform:
            valid = module_id == "platform" and permission_id.startswith("platform.")
        else:
            valid = module_id != "platform" and permission_id.startswith(f"{module_id}.")
            valid = valid and not permission_id.startswith("platform.")
        if not valid:
            raise InvalidPermissionNamespaceError(permission_id, module_id=module_id)


class LegacyRolePermissionResolver:
    """Temporary adapter from existing account roles to registered stable IDs."""

    def __init__(self, role_permissions: Mapping[str, Iterable[str]] | None = None) -> None:
        self._role_permissions = {
            role.strip().upper(): frozenset(permission_ids)
            for role, permission_ids in (role_permissions or {}).items()
        }

    def grants(self, subject: PermissionSubject, permission_id: str) -> bool:
        if subject.is_superuser:
            return True
        roles = {role.strip().upper() for role in (subject.roles or [])}
        return any(
            permission_id in self._role_permissions.get(role, ()) for role in roles
        )


class PermissionEngine:
    """Evaluates grants only for definitions active in the sealed registry."""

    def __init__(
        self,
        registry: PermissionRegistry,
        resolver: LegacyRolePermissionResolver | None = None,
    ) -> None:
        self.registry = registry
        self.resolver = resolver or LegacyRolePermissionResolver()

    def allows(self, subject: PermissionSubject, permission_id: str) -> bool:
        if self.registry.get(permission_id) is None:
            logger.warning(
                "Unknown permission denied",
                extra={"permission_id": permission_id, "permission_decision": "deny"},
            )
            return False
        allowed = self.resolver.grants(subject, permission_id)
        logger.info(
            "Permission evaluated",
            extra={
                "permission_id": permission_id,
                "permission_decision": "allow" if allowed else "deny",
            },
        )
        return allowed

    def snapshot(self, subject: PermissionSubject) -> tuple[str, ...]:
        return tuple(
            permission_id
            for permission_id in self.registry.permission_ids
            if self.resolver.grants(subject, permission_id)
        )


class RegistryPermissionPort:
    """Public SDK adapter; identity loading remains a host responsibility."""

    def __init__(
        self,
        engine: PermissionEngine,
        subject_loader: Callable[[str], Awaitable[PermissionSubject | None]],
    ) -> None:
        self._engine = engine
        self._subject_loader = subject_loader

    async def is_allowed(
        self,
        permission_id: str,
        *,
        principal_id: str | None,
        resource_id: str | None = None,
    ) -> bool:
        del resource_id
        if principal_id is None:
            return False
        subject = await self._subject_loader(principal_id)
        return subject is not None and self._engine.allows(subject, permission_id)
