"""Kleines Modul-Fixture für namespacete, typisierte Settings."""

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr

from app.platform.modules.sdk import (
    ModuleContext,
    ModuleDefinition,
    ModuleSettingsContribution,
    parse_manifest,
)


class ExampleModuleSettings(BaseModel):
    endpoint_url: AnyHttpUrl = Field(json_schema_extra={"public": True})
    timeout_seconds: int = Field(default=10, ge=1, le=120)
    api_token: SecretStr = Field(min_length=12)
    feature_enabled: bool = False
    label: str | None = None

    model_config = ConfigDict(frozen=True)


MANIFEST = parse_manifest(
    {
        "manifest_version": 1,
        "id": "settings-fixture",
        "name": "Settings Fixture",
        "version": "1.0.0",
        "requires": {"host": ">=0.2.0,<1.0.0", "sdk": ">=1.4.0,<2.0.0"},
        "config": {"namespace": "settings-fixture"},
    }
)


class SettingsFixtureModule:
    manifest = MANIFEST

    def __init__(self) -> None:
        self.settings: ExampleModuleSettings | None = None

    def register(self, context: ModuleContext) -> None:
        assert context.settings is not None
        self.settings = context.settings.require(ExampleModuleSettings)


DEFINITION = ModuleDefinition(
    manifest=MANIFEST,
    loader=SettingsFixtureModule,
    origin=__name__,
    declared_id=MANIFEST.id,
    settings=ModuleSettingsContribution(
        module_id=MANIFEST.id,
        namespace=MANIFEST.config.namespace,
        model=ExampleModuleSettings,
    ),
)
