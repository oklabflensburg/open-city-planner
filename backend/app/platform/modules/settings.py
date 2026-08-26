"""Host-owned Registry für typisierte, namespacete und secret-sichere Modulsettings."""

import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TypeVar, cast, get_args

from pydantic import BaseModel, SecretBytes, SecretStr, ValidationError
from pydantic_settings import BaseSettings, DotEnvSettingsSource, SettingsConfigDict

from app.platform.modules.errors import (
    DuplicateConfigNamespaceError,
    ModulePublicConfigError,
    ModuleSettingsError,
    ModuleSettingsNamespaceError,
    ModuleSettingsValidationError,
)
from app.platform.modules.manifest import ModuleManifestV1
from app.platform.modules.sdk import ModuleDefinition, ModuleSettingsContribution
from app.platform.modules.settings_namespace import (
    MODULE_ENV_PREFIX,
    is_module_environment_key,
    module_id_to_env_prefix,
)

TSettings = TypeVar("TSettings", bound=BaseModel)


class _ModuleEnvironmentReader(BaseSettings):
    model_config = SettingsConfigDict(extra="allow")


class ModuleSettingsRegistry:
    """Lädt aktive Modulschemas einmalig und gibt nur modulgebundene Adapter aus."""

    def __init__(self, environment: Mapping[str, str] | None = None) -> None:
        self._environment = {
            key.upper(): value
            for key, value in (environment or {}).items()
            if is_module_environment_key(key)
        }
        self._settings: dict[str, BaseModel] = {}
        self._models: dict[str, type[BaseModel]] = {}
        self._namespaces: dict[str, str] = {}
        self._public: dict[str, dict[str, object]] = {}
        self._sealed = False

    @property
    def sealed(self) -> bool:
        return self._sealed

    @property
    def public_config(self) -> dict[str, dict[str, object]]:
        return {namespace: dict(values) for namespace, values in self._public.items()}

    def register(
        self,
        manifest: ModuleManifestV1,
        contribution: ModuleSettingsContribution,
    ) -> None:
        if self._sealed:
            raise ModuleSettingsError(
                "Settings registration is closed.", module_id=manifest.id
            )
        self._validate_ownership(manifest, contribution)
        namespace = contribution.namespace
        existing_owner = self._namespaces.get(namespace)
        if existing_owner is not None:
            raise DuplicateConfigNamespaceError(namespace, (existing_owner, manifest.id))
        if not isinstance(contribution.model, type) or not issubclass(
            contribution.model, BaseModel
        ):
            raise ModuleSettingsValidationError(
                "The settings contribution must use a Pydantic BaseModel.",
                module_id=manifest.id,
                namespace=namespace,
            )
        if not contribution.model.model_config.get("frozen", False):
            raise ModuleSettingsValidationError(
                "Module settings models must be frozen after startup validation.",
                module_id=manifest.id,
                namespace=namespace,
            )

        public_fields = self._public_fields(manifest, contribution)
        settings = self._load(manifest, contribution)
        public_values = settings.model_dump(mode="json", include=public_fields)
        try:
            json.dumps(public_values, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ModulePublicConfigError(
                "The explicit public settings subset is not JSON-compatible.",
                module_id=manifest.id,
                namespace=namespace,
            ) from exc

        self._namespaces[namespace] = manifest.id
        self._models[manifest.id] = contribution.model
        self._settings[manifest.id] = settings
        self._public[namespace] = cast(dict[str, object], public_values)

    def bind(self, manifest: ModuleManifestV1) -> "ModuleSettingsAdapter | None":
        settings = self._settings.get(manifest.id)
        model = self._models.get(manifest.id)
        if settings is None or model is None:
            return None
        return ModuleSettingsAdapter(manifest.id, model, settings)

    def seal(self) -> None:
        self._sealed = True

    def _validate_ownership(
        self,
        manifest: ModuleManifestV1,
        contribution: ModuleSettingsContribution,
    ) -> None:
        declared_namespace = manifest.config.namespace if manifest.config is not None else None
        if contribution.module_id != manifest.id or contribution.namespace != declared_namespace:
            raise ModuleSettingsNamespaceError(
                "Manifest and settings contribution ownership must match exactly.",
                module_id=manifest.id,
                namespace=declared_namespace,
            )
        expected_prefix = module_id_to_env_prefix(manifest.id)
        actual_prefix = module_id_to_env_prefix(contribution.namespace)
        if expected_prefix != actual_prefix:
            raise ModuleSettingsNamespaceError(
                "The config namespace must derive from the owning module ID.",
                module_id=manifest.id,
                namespace=contribution.namespace,
            )

    def _load(
        self,
        manifest: ModuleManifestV1,
        contribution: ModuleSettingsContribution,
    ) -> BaseModel:
        prefix = module_id_to_env_prefix(contribution.namespace)
        fields_by_key = {
            f"{prefix}{field_name.upper()}": field_name
            for field_name in contribution.model.model_fields
        }
        unknown = sorted(
            key
            for key in self._environment
            if key.startswith(prefix) and key not in fields_by_key
        )
        if unknown:
            raise ModuleSettingsNamespaceError(
                "The active module environment contains an unknown settings key.",
                module_id=manifest.id,
                namespace=contribution.namespace,
                environment_key=unknown[0],
            )
        values = {
            field_name: self._environment[key]
            for key, field_name in fields_by_key.items()
            if key in self._environment
        }
        try:
            return contribution.model.model_validate(values)
        except ValidationError as exc:
            error = exc.errors(include_url=False, include_input=False)[0]
            location = error.get("loc", ())
            field_name = str(location[0]) if location else None
            environment_key = (
                f"{prefix}{field_name.upper()}" if field_name is not None else None
            )
            raise ModuleSettingsValidationError(
                "The active module configuration is missing or invalid.",
                module_id=manifest.id,
                namespace=contribution.namespace,
                field_name=field_name,
                environment_key=environment_key,
                error_type=str(error.get("type", "validation_error")),
            ) from exc

    def _public_fields(
        self,
        manifest: ModuleManifestV1,
        contribution: ModuleSettingsContribution,
    ) -> set[str]:
        public_fields: set[str] = set()
        for field_name, field in contribution.model.model_fields.items():
            metadata = field.json_schema_extra or {}
            if not isinstance(metadata, dict) or metadata.get("public") is not True:
                continue
            if _contains_secret_type(field.annotation):
                raise ModulePublicConfigError(
                    "Secret fields cannot be declared as public.",
                    module_id=manifest.id,
                    namespace=contribution.namespace,
                    field_name=field_name,
                )
            public_fields.add(field_name)
        return public_fields


class ModuleSettingsAdapter:
    """An ein Modul und genau einen Settings-Typ gebundener SDK-Adapter."""

    def __init__(
        self,
        module_id: str,
        model: type[BaseModel],
        settings: BaseModel,
    ) -> None:
        self._module_id = module_id
        self._model = model
        self._settings = settings

    def get(
        self,
        settings_type_or_key: type[TSettings] | str,
        default: object = None,
    ) -> TSettings | object | None:
        if isinstance(settings_type_or_key, str):
            return getattr(self._settings, settings_type_or_key, default)
        if settings_type_or_key is not self._model:
            return None
        return cast(TSettings, self._settings)

    def require(self, settings_type_or_key: type[TSettings] | str) -> TSettings | object:
        value = self.get(settings_type_or_key)
        if value is None:
            requested = (
                settings_type_or_key
                if isinstance(settings_type_or_key, str)
                else settings_type_or_key.__name__
            )
            raise ModuleSettingsError(
                "The requested setting or model is not owned by this module.",
                module_id=self._module_id,
                field_name=requested,
            )
        return value


def read_module_environment(
    *,
    env_file: Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Liest ausschließlich reservierte Modulschlüssel aus dotenv und Prozessumgebung."""

    values: dict[str, str] = {}
    if env_file is not None:
        source = DotEnvSettingsSource(
            _ModuleEnvironmentReader,
            env_file=env_file,
            env_file_encoding="utf-8",
        )
        values.update(
            {
                key.upper(): value
                for key, value in source.env_vars.items()
                if value is not None and is_module_environment_key(key)
            }
        )
    values.update(
        {
            key.upper(): value
            for key, value in (environment if environment is not None else os.environ).items()
            if is_module_environment_key(key)
        }
    )
    return values


def build_module_settings_registry(
    resolved_definitions: Sequence[tuple[ModuleDefinition, ModuleManifestV1]],
    *,
    registry: ModuleSettingsRegistry,
) -> ModuleSettingsRegistry:
    for definition, manifest in resolved_definitions:
        if definition.settings is None and manifest.config is None:
            continue
        if definition.settings is None or manifest.config is None:
            raise ModuleSettingsNamespaceError(
                "Active module manifest and definition must declare settings together.",
                module_id=manifest.id,
                namespace=manifest.config.namespace if manifest.config is not None else None,
            )
        registry.register(manifest, definition.settings)
    registry.seal()
    return registry


def _contains_secret_type(annotation: object, seen: frozenset[type[BaseModel]] = frozenset()) -> bool:
    if annotation in {SecretStr, SecretBytes}:
        return True
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        if annotation in seen:
            return False
        nested_seen = seen | {annotation}
        return any(
            _contains_secret_type(field.annotation, nested_seen)
            for field in annotation.model_fields.values()
        )
    return any(_contains_secret_type(argument, seen) for argument in get_args(annotation))


__all__ = [
    "MODULE_ENV_PREFIX",
    "ModuleSettingsAdapter",
    "ModuleSettingsRegistry",
    "build_module_settings_registry",
    "module_id_to_env_prefix",
    "read_module_environment",
]
