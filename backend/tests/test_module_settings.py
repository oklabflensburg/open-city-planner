import json
import logging
from pathlib import Path

import pytest
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from app.core.config import Settings
from app.platform.modules.context import ModuleContextFactory
from app.platform.modules.discovery import FirstPartyModuleDiscovery
from app.platform.modules.errors import (
    DuplicateConfigNamespaceError,
    ModulePublicConfigError,
    ModuleSettingsError,
    ModuleSettingsNamespaceError,
    ModuleSettingsValidationError,
)
from app.platform.modules.import_boundaries import find_host_settings_import_violations
from app.platform.modules.runtime import create_module_runtime
from app.platform.modules.sdk import ModuleDefinition, ModuleSettingsContribution
from app.platform.modules.settings import (
    ModuleSettingsRegistry,
    build_module_settings_registry,
    module_id_to_env_prefix,
    read_module_environment,
)
from app.platform.modules.testing import FakeModuleSettings, create_test_module_context
from tests.fixtures.settings_module import (
    DEFINITION,
    MANIFEST,
    ExampleModuleSettings,
    SettingsFixtureModule,
)
from tests.test_module_runtime import FakeDiscovery

SECRET_MARKER = "DO_NOT_LEAK_7f3e9a"
VALID_ENVIRONMENT = {
    "OCP_MODULE_SETTINGS_FIXTURE_ENDPOINT_URL": "https://example.org/api",
    "OCP_MODULE_SETTINGS_FIXTURE_API_TOKEN": "safe-test-token",
}


@pytest.mark.parametrize(
    ("module_id", "expected"),
    [
        ("analysis-areas", "OCP_MODULE_ANALYSIS_AREAS_"),
        ("analysis2", "OCP_MODULE_ANALYSIS2_"),
        ("a-b-c", "OCP_MODULE_A_B_C_"),
    ],
)
def test_module_id_has_deterministic_environment_prefix(
    module_id: str,
    expected: str,
) -> None:
    assert module_id_to_env_prefix(module_id) == expected


def test_defaults_overrides_optional_values_and_types_are_validated() -> None:
    registry = registry_for(
        {
            **VALID_ENVIRONMENT,
            "OCP_MODULE_SETTINGS_FIXTURE_TIMEOUT_SECONDS": "30",
            "OCP_MODULE_SETTINGS_FIXTURE_FEATURE_ENABLED": "true",
            "OCP_MODULE_SETTINGS_FIXTURE_LABEL": "Example",
        }
    )
    adapter = registry.bind(MANIFEST)
    assert adapter is not None

    settings = adapter.require(ExampleModuleSettings)
    assert settings.timeout_seconds == 30
    assert settings.feature_enabled is True
    assert settings.label == "Example"
    assert settings.api_token.get_secret_value() == "safe-test-token"


def test_default_and_missing_optional_setting_are_applied() -> None:
    adapter = registry_for(VALID_ENVIRONMENT).bind(MANIFEST)
    assert adapter is not None
    settings = adapter.require(ExampleModuleSettings)

    assert settings.timeout_seconds == 10
    assert settings.feature_enabled is False
    assert settings.label is None


@pytest.mark.parametrize(
    ("key", "value", "error_type"),
    [
        ("OCP_MODULE_SETTINGS_FIXTURE_TIMEOUT_SECONDS", "abc", "int_parsing"),
        ("OCP_MODULE_SETTINGS_FIXTURE_FEATURE_ENABLED", "perhaps", "bool_parsing"),
        ("OCP_MODULE_SETTINGS_FIXTURE_ENDPOINT_URL", "not-a-url", "url_parsing"),
    ],
)
def test_invalid_environment_type_has_safe_structured_error(
    key: str,
    value: str,
    error_type: str,
) -> None:
    with pytest.raises(ModuleSettingsValidationError) as error:
        registry_for({**VALID_ENVIRONMENT, key: value})

    assert error.value.module_id == "settings-fixture"
    assert error.value.namespace == "settings-fixture"
    assert error.value.environment_key == key
    assert error.value.error_type == error_type
    assert value not in str(error.value)


def test_active_module_missing_required_secret_fails_before_module_loading() -> None:
    loaded = False

    def loader():
        nonlocal loaded
        loaded = True
        return SettingsFixtureModule()

    definition = ModuleDefinition(
        manifest=DEFINITION.manifest,
        loader=loader,
        origin=DEFINITION.origin,
        declared_id=DEFINITION.declared_id,
        settings=DEFINITION.settings,
    )
    with pytest.raises(ModuleSettingsValidationError) as error:
        runtime_for(definition, {"OCP_MODULE_SETTINGS_FIXTURE_ENDPOINT_URL": "https://example.org"})

    assert not loaded
    assert error.value.field_name == "api_token"
    assert error.value.environment_key == "OCP_MODULE_SETTINGS_FIXTURE_API_TOKEN"


def test_disabled_module_does_not_validate_required_secret() -> None:
    runtime = create_module_runtime(
        enabled_module_ids=(),
        discovery_providers=(FakeDiscovery((DEFINITION,)),),
        host_version="0.2.0",
        context_factory=ModuleContextFactory(module_environment={}),
    )
    runtime.register(FastAPI())
    assert runtime.module_ids == ()


def test_runtime_binds_validated_settings_before_module_registration() -> None:
    runtime = runtime_for(DEFINITION, VALID_ENVIRONMENT)
    record = runtime.registry.get("settings-fixture")
    assert record.context.settings is not None

    runtime.register(FastAPI())

    module = record.module
    assert isinstance(module, SettingsFixtureModule)
    assert module.settings is record.context.settings.require(ExampleModuleSettings)
    assert runtime.public_module_config == {
        "settings-fixture": {"endpoint_url": "https://example.org/api"}
    }


def test_first_party_discovery_preserves_passive_settings_contribution() -> None:
    runtime = create_module_runtime(
        enabled_module_ids=(DEFINITION.declared_id,),
        discovery_providers=(
            FirstPartyModuleDiscovery({DEFINITION.declared_id: DEFINITION}),
        ),
        host_version="0.2.0",
        context_factory=ModuleContextFactory(module_environment=VALID_ENVIRONMENT),
    )
    runtime.register(FastAPI())
    assert runtime.registry.get(DEFINITION.declared_id).context.settings is not None


def test_settings_are_frozen_after_startup_validation() -> None:
    adapter = registry_for(VALID_ENVIRONMENT).bind(MANIFEST)
    assert adapter is not None
    settings = adapter.require(ExampleModuleSettings)
    with pytest.raises(ValidationError, match="frozen"):
        settings.timeout_seconds = 99  # type: ignore[misc]


def test_public_config_is_opt_in_json_and_secret_free() -> None:
    registry = registry_for(
        {
            **VALID_ENVIRONMENT,
            "OCP_MODULE_SETTINGS_FIXTURE_TIMEOUT_SECONDS": "30",
        }
    )
    payload = registry.public_config
    serialized = json.dumps(payload)

    assert payload == {"settings-fixture": {"endpoint_url": "https://example.org/api"}}
    assert "api_token" not in serialized
    assert "timeout_seconds" not in serialized
    assert "safe-test-token" not in serialized


def test_secret_is_masked_in_repr_exception_public_config_and_logs(caplog) -> None:
    environment = {
        **VALID_ENVIRONMENT,
        "OCP_MODULE_SETTINGS_FIXTURE_API_TOKEN": SECRET_MARKER,
        "OCP_MODULE_SETTINGS_FIXTURE_TIMEOUT_SECONDS": SECRET_MARKER,
    }
    with caplog.at_level(logging.DEBUG), pytest.raises(ModuleSettingsValidationError) as error:
        registry_for(environment)

    assert SECRET_MARKER not in str(error.value)
    assert SECRET_MARKER not in repr(error.value)
    assert SECRET_MARKER not in caplog.text

    valid = registry_for(
        {**VALID_ENVIRONMENT, "OCP_MODULE_SETTINGS_FIXTURE_API_TOKEN": SECRET_MARKER}
    )
    adapter = valid.bind(MANIFEST)
    assert adapter is not None
    settings = adapter.require(ExampleModuleSettings)
    assert SECRET_MARKER not in repr(settings)
    assert SECRET_MARKER not in json.dumps(valid.public_config)
    assert settings.api_token.get_secret_value() == SECRET_MARKER


def test_secret_field_cannot_be_declared_public() -> None:
    class UnsafeSettings(BaseModel):
        api_token: SecretStr = Field(json_schema_extra={"public": True})

        model_config = ConfigDict(frozen=True)

    contribution = ModuleSettingsContribution(
        module_id=MANIFEST.id,
        namespace=MANIFEST.config.namespace,
        model=UnsafeSettings,
    )
    with pytest.raises(ModulePublicConfigError, match="cannot be declared as public"):
        ModuleSettingsRegistry({}).register(MANIFEST, contribution)


def test_nested_secret_model_cannot_be_declared_public() -> None:
    class Credentials(BaseModel):
        token: SecretStr

        model_config = ConfigDict(frozen=True)

    class UnsafeNestedSettings(BaseModel):
        credentials: Credentials = Field(json_schema_extra={"public": True})

        model_config = ConfigDict(frozen=True)

    contribution = ModuleSettingsContribution(
        module_id=MANIFEST.id,
        namespace=MANIFEST.config.namespace,
        model=UnsafeNestedSettings,
    )
    with pytest.raises(ModulePublicConfigError, match="cannot be declared as public"):
        ModuleSettingsRegistry({}).register(MANIFEST, contribution)


def test_manifest_contribution_namespace_and_ownership_must_match() -> None:
    contribution = ModuleSettingsContribution(
        module_id="foreign-module",
        namespace=MANIFEST.config.namespace,
        model=ExampleModuleSettings,
    )
    with pytest.raises(ModuleSettingsNamespaceError):
        ModuleSettingsRegistry(VALID_ENVIRONMENT).register(MANIFEST, contribution)


def test_manifest_and_definition_must_declare_settings_together() -> None:
    definition_without_settings = ModuleDefinition(
        manifest=MANIFEST,
        loader=SettingsFixtureModule,
        origin="test:missing-settings",
        declared_id=MANIFEST.id,
    )
    with pytest.raises(ModuleSettingsNamespaceError, match="declare settings together"):
        build_module_settings_registry(
            ((definition_without_settings, MANIFEST),),
            registry=ModuleSettingsRegistry(VALID_ENVIRONMENT),
        )


def test_mutable_settings_model_is_rejected() -> None:
    class MutableSettings(BaseModel):
        value: str = "default"

    contribution = ModuleSettingsContribution(
        module_id=MANIFEST.id,
        namespace=MANIFEST.config.namespace,
        model=MutableSettings,
    )
    with pytest.raises(ModuleSettingsValidationError, match="must be frozen"):
        ModuleSettingsRegistry({}).register(MANIFEST, contribution)


def test_duplicate_namespace_reuses_manifest_error() -> None:
    registry = ModuleSettingsRegistry(VALID_ENVIRONMENT)
    assert DEFINITION.settings is not None
    registry.register(MANIFEST, DEFINITION.settings)
    with pytest.raises(DuplicateConfigNamespaceError):
        registry.register(MANIFEST, DEFINITION.settings)


def test_unknown_active_module_environment_key_is_rejected_without_value() -> None:
    key = "OCP_MODULE_SETTINGS_FIXTURE_TYPO"
    with pytest.raises(ModuleSettingsNamespaceError) as error:
        registry_for({**VALID_ENVIRONMENT, key: SECRET_MARKER})
    assert error.value.environment_key == key
    assert SECRET_MARKER not in str(error.value)


def test_module_adapter_cannot_access_another_settings_type() -> None:
    class ForeignSettings(BaseModel):
        value: str

    adapter = registry_for(VALID_ENVIRONMENT).bind(MANIFEST)
    assert adapter is not None
    assert adapter.get(ForeignSettings) is None
    with pytest.raises(ModuleSettingsError):
        adapter.require(ForeignSettings)


def test_registry_is_sealed_after_bootstrap() -> None:
    registry = registry_for(VALID_ENVIRONMENT)
    assert registry.sealed
    assert DEFINITION.settings is not None
    with pytest.raises(ModuleSettingsError, match="closed"):
        registry.register(MANIFEST, DEFINITION.settings)


def test_dotenv_module_keys_are_reserved_for_registry_but_other_typos_fail(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / "backend.env"
    env_file.write_text(
        "OCP_MODULE_SETTINGS_FIXTURE_API_TOKEN=from-file\n",
        encoding="utf-8",
    )
    Settings(_env_file=env_file)
    assert read_module_environment(env_file=env_file, environment={}) == {
        "OCP_MODULE_SETTINGS_FIXTURE_API_TOKEN": "from-file"
    }

    env_file.write_text("UNKNOWN_HOST_SETTING=typo\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="extra_forbidden"):
        Settings(_env_file=env_file)


def test_fake_module_settings_supports_typed_model() -> None:
    model = ExampleModuleSettings.model_validate(
        {
            "endpoint_url": "https://example.org",
            "api_token": "safe-test-token",
        }
    )
    fake = FakeModuleSettings(model=model)
    context = create_test_module_context(settings_model=model)

    assert fake.require(ExampleModuleSettings) is model
    assert context.settings is not None
    assert context.settings.require(ExampleModuleSettings) is model


def test_modular_fixtures_do_not_import_host_core_settings() -> None:
    fixtures = Path(__file__).parent / "fixtures"
    assert find_host_settings_import_violations(fixtures) == ()


def test_direct_host_settings_import_has_actionable_error(tmp_path: Path) -> None:
    source = tmp_path / "modules/example/module.py"
    source.parent.mkdir(parents=True)
    source.write_text("from app.core.config import get_settings\n", encoding="utf-8")

    violations = find_host_settings_import_violations(tmp_path / "modules")

    assert len(violations) == 1
    assert violations[0].module_id == "example"
    assert violations[0].source == source
    assert "context.settings" in str(violations[0])


def registry_for(environment: dict[str, str]) -> ModuleSettingsRegistry:
    registry = ModuleSettingsRegistry(environment)
    build_module_settings_registry(((DEFINITION, MANIFEST),), registry=registry)
    return registry


def runtime_for(definition: ModuleDefinition, environment: dict[str, str]):
    return create_module_runtime(
        enabled_module_ids=(definition.declared_id,),
        discovery_providers=(FakeDiscovery((definition,)),),
        host_version="0.2.0",
        context_factory=ModuleContextFactory(module_environment=environment),
    )
