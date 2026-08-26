"""Stable permission contracts owned by the legacy Social Publishing domain."""

from app.platform.modules.sdk import PermissionDefinition

SOCIAL_PUBLISH = "social.publish"
SOCIAL_PERMISSION_DEFINITIONS = (
    PermissionDefinition(
        id=SOCIAL_PUBLISH,
        module_id="social",
        description="Social-Publishing verwalten und Veröffentlichungen freigeben",
        category="administration",
    ),
)
