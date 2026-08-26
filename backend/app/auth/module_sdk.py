"""Host-Auth-Adapter für permission-geschützte Routen externer Module."""

from typing import Annotated

from fastapi import Depends

from app.auth.dependencies import require_permission
from app.platform.modules.sdk import ModulePrincipal


class HostPermissionDependencies:
    """Gibt Modulen nur eine stabile Principal-ID statt privater User-Typen."""

    def require(self, permission_id: str, *, csrf: bool = False):
        host_dependency = require_permission(permission_id, csrf=csrf)

        async def dependency(
            user: Annotated[object, Depends(host_dependency)],
        ) -> ModulePrincipal:
            principal_id = getattr(user, "id", None)
            if principal_id is None:
                raise TypeError("The authenticated host principal has no stable ID.")
            return ModulePrincipal(id=str(principal_id))

        return dependency
