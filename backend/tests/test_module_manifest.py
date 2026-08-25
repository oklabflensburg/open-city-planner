import itertools
import json
from pathlib import Path
from typing import Any

import pytest

from app.platform.modules import (
    DuplicateConfigNamespaceError,
    DuplicateModuleIdError,
    InvalidRuntimeVersionError,
    MissingModuleDependencyError,
    ModuleCompatibilityError,
    ModuleDependencyCycleError,
    ModuleDependencyVersionError,
    ModuleManifestError,
    ModuleSelfDependencyError,
    UnsupportedManifestVersionError,
    module_manifest_json_schema,
    parse_manifest,
    resolve_module_order,
    validate_manifest,
    validate_manifests,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "docs/modules/schema/module-manifest-v1.schema.json"
EXAMPLES_PATH = ROOT / "docs/modules/examples"


def manifest_data(
    module_id: str = "example-module",
    *,
    version: str = "1.0.0",
    required_modules: dict[str, str] | None = None,
    optional_modules: dict[str, str] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "manifest_version": 1,
        "id": module_id,
        "name": module_id.replace("-", " ").title(),
        "version": version,
        "requires": {
            "host": ">=1.0.0,<2.0.0",
            "sdk": ">=1.0.0,<2.0.0",
            "modules": required_modules or {},
        },
    }
    if optional_modules is not None:
        data["optional"] = {"modules": optional_modules}
    data.update(overrides)
    return data


def parsed_manifest(module_id: str = "example-module", **kwargs: Any):
    return parse_manifest(manifest_data(module_id, **kwargs))


def module_ids(manifests) -> list[str]:
    return [manifest.id for manifest in manifests]


def test_parse_minimal_manifest() -> None:
    manifest = parsed_manifest()

    assert manifest.id == "example-module"
    assert manifest.version == "1.0.0"
    assert manifest.backend is None
    assert manifest.frontend is None
    assert manifest.optional.modules == {}


def test_parse_full_manifest() -> None:
    manifest = parse_manifest(
        manifest_data(
            "example-biotopes",
            version="2.3.1",
            required_modules={"example-layer-catalog": ">=1.0.0,<2.0.0"},
            optional_modules={"example-statistics": ">=1.0.0"},
            backend={"package": "open_city_planner_biotopes"},
            frontend={"package": "@open-city-planner/biotopes"},
            capabilities=["map.layer", "map.feature-info", "analysis.provider"],
            permissions=["example-biotopes.read", "example-biotopes.admin"],
            config={"namespace": "example-biotopes"},
            persistence={"schema": "example_biotopes", "migrations": True},
        )
    )

    assert manifest.backend and manifest.backend.package == "open_city_planner_biotopes"
    assert manifest.frontend and manifest.frontend.package == "@open-city-planner/biotopes"
    assert manifest.persistence and manifest.persistence.schema_name == "example_biotopes"
    assert manifest.model_dump(by_alias=True)["persistence"]["schema"] == "example_biotopes"


@pytest.mark.parametrize(
    ("backend", "frontend"),
    [
        ({"package": "example_backend"}, None),
        (None, {"package": "@open-city-planner/example"}),
        ({"package": "example_backend"}, {"package": "example-frontend"}),
    ],
)
def test_backend_only_frontend_only_and_combined_manifests(backend, frontend) -> None:
    manifest = parse_manifest(manifest_data(backend=backend, frontend=frontend))

    assert (manifest.backend is not None) == (backend is not None)
    assert (manifest.frontend is not None) == (frontend is not None)


@pytest.mark.parametrize(
    "module_id",
    ["Analysis-Areas", "analysis_areas", "analysis--areas", "analysis-", "1-analysis"],
)
def test_invalid_module_id_is_rejected(module_id: str) -> None:
    with pytest.raises(ModuleManifestError, match="Invalid module manifest"):
        parse_manifest(manifest_data(module_id))


@pytest.mark.parametrize("version", ["1.0", "v1.0.0", "1.0.0.0", "latest"])
def test_invalid_module_version_is_rejected(version: str) -> None:
    with pytest.raises(ModuleManifestError, match="complete SemVer"):
        parsed_manifest(version=version)


@pytest.mark.parametrize(
    "version_range",
    ["^1.2.0", "~1.2.0", ">=1.2", ">=1.2.0, <2.0.0", "*"],
)
def test_only_canonical_explicit_version_ranges_are_accepted(version_range: str) -> None:
    data = manifest_data()
    data["requires"]["host"] = version_range

    with pytest.raises(ModuleManifestError, match="SemVer|range clauses"):
        parse_manifest(data)


def test_unsupported_manifest_version_has_structured_error() -> None:
    with pytest.raises(UnsupportedManifestVersionError) as exc_info:
        parse_manifest({**manifest_data(), "manifest_version": 999}, origin="module.json")

    assert exc_info.value.manifest_version == 999
    assert exc_info.value.origin == "module.json"


def test_unknown_manifest_field_is_rejected() -> None:
    with pytest.raises(ModuleManifestError) as exc_info:
        parse_manifest({**manifest_data(), "permisions": ["example-module.read"]})

    assert any(detail["type"] == "extra_forbidden" for detail in exc_info.value.details)


def test_persistence_internal_field_name_is_not_accepted_as_manifest_alias() -> None:
    with pytest.raises(ModuleManifestError):
        parse_manifest(manifest_data(persistence={"schema_name": "example_module"}))


@pytest.mark.parametrize(
    "overrides",
    [
        {"manifest_version": True},
        {"version": 1},
        {"persistence": {"schema": "example_module", "migrations": "true"}},
    ],
)
def test_manifest_values_are_not_coerced(overrides: dict[str, Any]) -> None:
    with pytest.raises(ModuleManifestError):
        parse_manifest(manifest_data(**overrides))


@pytest.mark.parametrize(
    ("field", "values"),
    [
        ("capabilities", ["map.layer", "map.layer"]),
        ("permissions", ["example-module.read", "example-module.read"]),
    ],
)
def test_duplicate_capabilities_and_permissions_are_rejected(field, values) -> None:
    with pytest.raises(ModuleManifestError, match="duplicate identifiers"):
        parse_manifest(manifest_data(**{field: values}))


def test_unknown_well_formed_capability_is_forward_compatible() -> None:
    manifest = parse_manifest(manifest_data(capabilities=["future.unlisted-capability"]))

    assert manifest.capabilities == ["future.unlisted-capability"]


def test_permissions_must_be_owned_by_the_module_namespace() -> None:
    with pytest.raises(ModuleManifestError, match="example-module\\."):
        parse_manifest(manifest_data(permissions=["other-module.admin"]))


@pytest.mark.parametrize("namespace", ["Example", "example_namespace", "example--config"])
def test_invalid_config_namespace_is_rejected(namespace: str) -> None:
    with pytest.raises(ModuleManifestError):
        parse_manifest(manifest_data(config={"namespace": namespace}))


def test_compatible_host_and_sdk_versions_are_accepted() -> None:
    manifest = parsed_manifest()

    assert validate_manifest(manifest, host_version="1.5.0", sdk_version="1.9.9") is manifest


@pytest.mark.parametrize(
    ("target", "host_version", "sdk_version", "found"),
    [
        ("host", "0.9.9", "1.0.0", "0.9.9"),
        ("host", "2.0.0", "1.0.0", "2.0.0"),
        ("sdk", "1.0.0", "2.0.0", "2.0.0"),
    ],
)
def test_incompatible_host_or_sdk_version_has_structured_error(
    target: str, host_version: str, sdk_version: str, found: str
) -> None:
    with pytest.raises(ModuleCompatibilityError) as exc_info:
        validate_manifest(
            parsed_manifest(),
            host_version=host_version,
            sdk_version=sdk_version,
        )

    assert exc_info.value.target == target
    assert exc_info.value.expected == ">=1.0.0,<2.0.0"
    assert exc_info.value.found == found


def test_invalid_runtime_version_is_rejected() -> None:
    with pytest.raises(InvalidRuntimeVersionError, match="host"):
        validate_manifest(parsed_manifest(), host_version="latest", sdk_version="1.0.0")


def test_required_dependency_is_validated() -> None:
    dependency = parsed_manifest("example-layer-catalog", version="1.5.0")
    consumer = parsed_manifest(
        "example-biotopes",
        required_modules={"example-layer-catalog": ">=1.0.0,<2.0.0"},
    )

    assert validate_manifests(
        [consumer, dependency], host_version="1.0.0", sdk_version="1.0.0"
    ) == (consumer, dependency)


def test_missing_required_dependency_has_structured_error() -> None:
    consumer = parsed_manifest(
        "example-biotopes",
        required_modules={"example-layer-catalog": ">=1.0.0,<2.0.0"},
    )

    with pytest.raises(MissingModuleDependencyError) as exc_info:
        validate_manifests([consumer], host_version="1.0.0", sdk_version="1.0.0")

    assert exc_info.value.dependency_id == "example-layer-catalog"
    assert exc_info.value.expected == ">=1.0.0,<2.0.0"


def test_incompatible_required_dependency_has_structured_error() -> None:
    dependency = parsed_manifest("example-layer-catalog", version="2.1.0")
    consumer = parsed_manifest(
        "example-biotopes",
        required_modules={"example-layer-catalog": ">=1.0.0,<2.0.0"},
    )

    with pytest.raises(ModuleDependencyVersionError) as exc_info:
        validate_manifests(
            [consumer, dependency], host_version="1.0.0", sdk_version="1.0.0"
        )

    assert exc_info.value.optional is False
    assert exc_info.value.found == "2.1.0"


def test_missing_optional_dependency_is_accepted() -> None:
    consumer = parsed_manifest(
        "example-biotopes",
        optional_modules={"example-statistics": ">=1.0.0,<2.0.0"},
    )

    validate_manifests([consumer], host_version="1.0.0", sdk_version="1.0.0")


def test_present_compatible_optional_dependency_is_accepted() -> None:
    dependency = parsed_manifest("example-statistics", version="1.5.0")
    consumer = parsed_manifest(
        "example-biotopes",
        optional_modules={"example-statistics": ">=1.0.0,<2.0.0"},
    )

    validate_manifests(
        [consumer, dependency], host_version="1.0.0", sdk_version="1.0.0"
    )


def test_present_incompatible_optional_dependency_is_rejected() -> None:
    dependency = parsed_manifest("example-statistics", version="2.0.0")
    consumer = parsed_manifest(
        "example-biotopes",
        optional_modules={"example-statistics": ">=1.0.0,<2.0.0"},
    )

    with pytest.raises(ModuleDependencyVersionError) as exc_info:
        validate_manifests(
            [consumer, dependency], host_version="1.0.0", sdk_version="1.0.0"
        )

    assert exc_info.value.optional is True


def test_dependency_cannot_be_both_required_and_optional() -> None:
    with pytest.raises(ModuleManifestError, match="both required and optional"):
        parsed_manifest(
            required_modules={"example-statistics": ">=1.0.0"},
            optional_modules={"example-statistics": ">=1.0.0"},
        )


@pytest.mark.parametrize("optional", [False, True])
def test_self_dependency_is_rejected(optional: bool) -> None:
    kwargs = (
        {"optional_modules": {"example-module": ">=1.0.0"}}
        if optional
        else {"required_modules": {"example-module": ">=1.0.0"}}
    )

    with pytest.raises(ModuleSelfDependencyError) as exc_info:
        validate_manifest(
            parsed_manifest(**kwargs), host_version="1.0.0", sdk_version="1.0.0"
        )

    assert exc_info.value.optional is optional


def test_duplicate_module_ids_fail_fast_and_include_origins() -> None:
    first = parsed_manifest("example-module")
    second = parsed_manifest("example-module", version="2.0.0")

    with pytest.raises(DuplicateModuleIdError) as exc_info:
        validate_manifests(
            [first, second],
            host_version="1.0.0",
            sdk_version="1.0.0",
            origins=["first.json", "second.json"],
        )

    assert exc_info.value.origins == ("first.json", "second.json")
    assert "first.json" in str(exc_info.value)


def test_duplicate_config_namespaces_are_rejected() -> None:
    first = parsed_manifest("module-a", config={"namespace": "shared-config"})
    second = parsed_manifest("module-b", config={"namespace": "shared-config"})

    with pytest.raises(DuplicateConfigNamespaceError):
        validate_manifests([first, second], host_version="1.0.0", sdk_version="1.0.0")


def test_graph_without_dependencies_is_lexicographic() -> None:
    manifests = [parsed_manifest("module-c"), parsed_manifest("module-a"), parsed_manifest("module-b")]

    assert module_ids(resolve_module_order(manifests)) == ["module-a", "module-b", "module-c"]


def test_linear_dependency_order() -> None:
    first = parsed_manifest("module-a")
    second = parsed_manifest("module-b", required_modules={"module-a": ">=1.0.0"})
    third = parsed_manifest("module-c", required_modules={"module-b": ">=1.0.0"})

    assert module_ids(resolve_module_order([third, first, second])) == [
        "module-a",
        "module-b",
        "module-c",
    ]


def test_diamond_dependency_order_is_deterministic() -> None:
    root = parsed_manifest("module-a")
    left = parsed_manifest("module-b", required_modules={"module-a": ">=1.0.0"})
    right = parsed_manifest("module-c", required_modules={"module-a": ">=1.0.0"})
    tip = parsed_manifest(
        "module-d",
        required_modules={"module-b": ">=1.0.0", "module-c": ">=1.0.0"},
    )

    assert module_ids(resolve_module_order([tip, right, left, root])) == [
        "module-a",
        "module-b",
        "module-c",
        "module-d",
    ]


def test_load_order_is_independent_of_input_order() -> None:
    manifests = [
        parsed_manifest("module-a"),
        parsed_manifest("module-b"),
        parsed_manifest("module-c", required_modules={"module-a": ">=1.0.0"}),
    ]

    orders = {
        tuple(module_ids(resolve_module_order(permutation)))
        for permutation in itertools.permutations(manifests)
    }

    assert orders == {("module-a", "module-b", "module-c")}


def test_present_optional_dependency_loads_before_consumer() -> None:
    dependency = parsed_manifest("module-b")
    consumer = parsed_manifest("module-a", optional_modules={"module-b": ">=1.0.0"})

    assert module_ids(resolve_module_order([consumer, dependency])) == ["module-b", "module-a"]


@pytest.mark.parametrize(
    ("manifests", "cycle"),
    [
        (
            [
                parsed_manifest("module-a", required_modules={"module-b": ">=1.0.0"}),
                parsed_manifest("module-b", required_modules={"module-a": ">=1.0.0"}),
            ],
            ("module-a", "module-b", "module-a"),
        ),
        (
            [
                parsed_manifest("module-a", required_modules={"module-b": ">=1.0.0"}),
                parsed_manifest("module-b", required_modules={"module-c": ">=1.0.0"}),
                parsed_manifest("module-c", required_modules={"module-a": ">=1.0.0"}),
            ],
            ("module-a", "module-b", "module-c", "module-a"),
        ),
    ],
)
def test_direct_and_indirect_cycles_report_the_cycle_path(manifests, cycle) -> None:
    with pytest.raises(ModuleDependencyCycleError) as exc_info:
        resolve_module_order(manifests)

    assert exc_info.value.cycle == cycle
    assert " -> ".join(cycle) in str(exc_info.value)


def test_graph_rejects_duplicate_module_ids() -> None:
    manifest = parsed_manifest()

    with pytest.raises(DuplicateModuleIdError):
        resolve_module_order([manifest, manifest])


def test_committed_json_schema_matches_pydantic_source_of_truth() -> None:
    committed_schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert committed_schema == module_manifest_json_schema()


def test_documentation_examples_match_schema_v1() -> None:
    manifests = [
        parse_manifest(json.loads(path.read_text(encoding="utf-8")), origin=str(path))
        for path in sorted(EXAMPLES_PATH.glob("*.module.json"))
    ]

    validated = validate_manifests(
        manifests,
        host_version="1.0.0",
        sdk_version="1.0.0",
        origins=[str(path) for path in sorted(EXAMPLES_PATH.glob("*.module.json"))],
    )

    assert module_ids(resolve_module_order(validated)) == [
        "example-layer-catalog",
        "example-biotopes",
        "example-pois",
    ]
