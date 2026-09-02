from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
import pytest

from app.cli import modules as modules_cli
from app.platform.modules.bundle import staged_ocp_bundle
from app.platform.modules.installer import read_modules_lock
from app.platform.modules.registry import (
    DEFAULT_REGISTRY_URL,
    REGISTRY_URL_ENV,
    ModuleRegistryClient,
    ModuleRegistryError,
    ModuleRegistryHTTPError,
    ModuleRegistryIntegrityError,
    ModuleRegistryValidationError,
)
from tests.test_module_bundle import _bundle
from tests.test_module_installer import _installer

BASE_URL = "https://registry.test"


def _documents(bundle: Path) -> dict[str, bytes]:
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    publisher = {"id": "fixture-publisher", "name": "Fixture Publisher"}
    index = {
        "schema_version": 1,
        "modules": [
            {
                "id": "registry-module",
                "name": "Registry Module",
                "publisher": publisher,
                "classification": "first-party",
                "channels": {
                    "stable": {"version": "1.0.0", "sha256": digest},
                },
                "metadata": "/modules/registry-module.json",
            }
        ],
    }
    metadata = {
        "schema_version": 1,
        "id": "registry-module",
        "name": "Registry Module",
        "description": "Hermetic fixture.",
        "publisher": publisher,
        "classification": "first-party",
        "source_repository": "https://github.com/example/ocp-module",
        "license": "AGPL-3.0-only",
        "versions": [
            {
                "version": "1.0.0",
                "channel": "stable",
                "artifact": {
                    "url": (f"{BASE_URL}/modules/registry-module/1.0.0/registry-module-1.0.0.ocp"),
                    "sha256": digest,
                },
                "bundle_format_version": 1,
                "source_commit": "a" * 40,
                "source_tag": "v1.0.0",
                "requires": {
                    "host": ">=0.2.0,<1.0.0",
                    "sdk": ">=1.7.0,<2.0.0",
                    "modules": {},
                },
            }
        ],
    }
    return {
        "/index.json": json.dumps(index).encode(),
        "/modules/registry-module.json": json.dumps(metadata).encode(),
        "/modules/registry-module/1.0.0/registry-module-1.0.0.ocp": (bundle.read_bytes()),
    }


def _client(
    documents: dict[str, bytes],
    *,
    headers: dict[str, dict[str, str]] | None = None,
    max_bundle_size: int | None = None,
) -> ModuleRegistryClient:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = documents.get(request.url.path)
        if payload is None:
            return httpx.Response(404, request=request)
        return httpx.Response(
            200,
            content=payload,
            headers=(headers or {}).get(request.url.path),
            request=request,
        )

    arguments: dict[str, object] = {
        "transport": httpx.MockTransport(handler),
    }
    if max_bundle_size is not None:
        arguments["max_bundle_size"] = max_bundle_size
    return ModuleRegistryClient(BASE_URL, **arguments)  # type: ignore[arg-type]


def _decoded(documents: dict[str, bytes], path: str) -> dict[str, object]:
    return json.loads(documents[path])


def _replace_json(
    documents: dict[str, bytes],
    path: str,
    value: dict[str, object],
) -> None:
    documents[path] = json.dumps(value).encode()


def _install_from_client(
    client: ModuleRegistryClient,
    state: Path,
    *,
    version: str | None = None,
    channel: str | None = None,
    expected_sha256: str | None = None,
):
    release = client.resolve(
        "registry-module",
        version=version,
        channel=channel,  # type: ignore[arg-type]
        expected_sha256=expected_sha256,
    )
    installer = _installer(state)
    with (
        client.download(release) as downloaded,
        staged_ocp_bundle(downloaded.path) as (package_root, package),
    ):
        client.validate_bundle(release, package)
        entry = installer.install(package_root)
    return release, entry, installer


def test_stable_default_exact_version_pin_and_idempotence(tmp_path: Path) -> None:
    bundle, _ = _bundle(
        tmp_path,
        "registry-module",
        backend=False,
        frontend=True,
    )
    documents = _documents(bundle)
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()

    with _client(documents) as client:
        default_release, entry, installer = _install_from_client(
            client,
            tmp_path / "state",
            expected_sha256=digest,
        )
        assert default_release.channel == "stable"
        assert default_release.version == "1.0.0"
        assert entry.enabled is False
        assert read_modules_lock(installer.lock_path).modules == (entry,)

        exact_release, repeated, _ = _install_from_client(
            client,
            tmp_path / "state",
            version="1.0.0",
        )
        assert exact_release.version == "1.0.0"
        assert repeated == entry

        channel_release = client.resolve("registry-module", channel="stable")
        assert channel_release.sha256 == digest


def test_cli_install_registry_reports_disabled_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, _ = _bundle(tmp_path, "registry-module", backend=False)
    documents = _documents(bundle)
    installer = _installer(tmp_path / "state")
    monkeypatch.setattr(modules_cli, "_installer", lambda _root: installer)
    monkeypatch.setattr(modules_cli, "_registry_client", lambda _url: _client(documents))

    result = modules_cli.main(["install-registry", "registry-module"])

    assert result == 0
    output = capsys.readouterr().out
    assert '"channel":"stable"' in output
    assert '"enabled":false' in output
    assert "installed as disabled" in output


def test_cli_rejects_version_and_channel_together() -> None:
    with pytest.raises(SystemExit) as error:
        modules_cli.main(
            [
                "install-registry",
                "registry-module",
                "--version",
                "1.0.0",
                "--channel",
                "stable",
            ]
        )
    assert error.value.code == 2


def test_registry_url_default_environment_and_security(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(REGISTRY_URL_ENV, raising=False)
    with ModuleRegistryClient() as client:
        assert client.base_url == DEFAULT_REGISTRY_URL
    monkeypatch.setenv(REGISTRY_URL_ENV, BASE_URL)
    with ModuleRegistryClient() as client:
        assert client.base_url == BASE_URL
    for unsafe in ("http://registry.test", "https://user:secret@registry.test"):
        with pytest.raises(ModuleRegistryValidationError, match="HTTPS|credentials"):
            ModuleRegistryClient(unsafe)


@pytest.mark.parametrize(
    ("mutation", "expected"),
    (
        ("unknown-module", "not present"),
        ("unknown-channel", "not available"),
        ("unknown-version", "not available"),
        ("index-schema", "schema_version"),
        ("metadata-schema", "schema_version"),
        ("index-extra", "unexpected"),
        ("metadata-extra", "unexpected"),
        ("metadata-id", "module ID conflicts"),
        ("publisher", "publisher conflicts"),
        ("classification", "classification conflicts"),
        ("channel", "channel conflicts"),
        ("index-digest", "index digest conflicts"),
        ("deployment-digest", "deployment SHA-256 conflicts"),
        ("artifact-url", "artifact URL"),
    ),
)
def test_resolution_failures_are_specific_and_do_not_create_state(
    tmp_path: Path,
    mutation: str,
    expected: str,
) -> None:
    bundle, _ = _bundle(tmp_path, "registry-module", backend=False)
    documents = _documents(bundle)
    index = _decoded(documents, "/index.json")
    metadata = _decoded(documents, "/modules/registry-module.json")
    module = index["modules"][0]
    release = metadata["versions"][0]
    module_id = "registry-module"
    channel = None
    version = None
    pin = None
    if mutation == "unknown-module":
        module_id = "missing-module"
    elif mutation == "unknown-channel":
        channel = "beta"
    elif mutation == "unknown-version":
        version = "2.0.0"
    elif mutation == "index-schema":
        index["schema_version"] = 2
    elif mutation == "metadata-schema":
        metadata["schema_version"] = 2
    elif mutation == "index-extra":
        index["unexpected"] = True
    elif mutation == "metadata-extra":
        metadata["unexpected"] = True
    elif mutation == "metadata-id":
        metadata["id"] = "different-module"
    elif mutation == "publisher":
        metadata["publisher"] = {"id": "different", "name": "Different"}
    elif mutation == "classification":
        metadata["classification"] = "reviewed-community"
    elif mutation == "channel":
        release["channel"] = "beta"
    elif mutation == "index-digest":
        module["channels"]["stable"]["sha256"] = "0" * 64
    elif mutation == "deployment-digest":
        pin = "0" * 64
    elif mutation == "artifact-url":
        release["artifact"]["url"] = "http://registry.test/module.ocp"
    _replace_json(documents, "/index.json", index)
    _replace_json(documents, "/modules/registry-module.json", metadata)

    with _client(documents) as client, pytest.raises(ModuleRegistryError, match=expected):
        client.resolve(
            module_id,
            version=version,
            channel=channel,  # type: ignore[arg-type]
            expected_sha256=pin,
        )
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize(
    "reference",
    (
        "https://evil.test/modules/registry-module.json",
        "/modules/../secrets.json",
        "/modules/%2e%2e/secrets.json",
        "//evil.test/modules/registry-module.json",
        "/modules/registry-module.json?token=secret",
    ),
)
def test_unsafe_metadata_references_are_rejected(tmp_path: Path, reference: str) -> None:
    bundle, _ = _bundle(tmp_path, "registry-module", backend=False)
    documents = _documents(bundle)
    index = _decoded(documents, "/index.json")
    index["modules"][0]["metadata"] = reference
    _replace_json(documents, "/index.json", index)

    with (
        _client(documents) as client,
        pytest.raises(ModuleRegistryValidationError, match="metadata reference"),
    ):
        client.resolve("registry-module")


@pytest.mark.parametrize("module_id", ("Uppercase", "../module", "two--dashes"))
def test_invalid_module_ids_are_rejected_before_http(module_id: str) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(500, request=request)

    with (
        ModuleRegistryClient(
            BASE_URL,
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(ModuleRegistryValidationError, match="Invalid registry selection"),
    ):
        client.resolve(module_id)
    assert requests == []


def test_tampered_bundle_cleanup_and_no_installer_state(tmp_path: Path) -> None:
    bundle, _ = _bundle(tmp_path, "registry-module", backend=False)
    documents = _documents(bundle)
    documents["/modules/registry-module/1.0.0/registry-module-1.0.0.ocp"] += b"tampered"
    observed: Path | None = None

    with (
        _client(documents) as client,
        pytest.raises(ModuleRegistryIntegrityError, match="Downloaded bundle"),
    ):
        release = client.resolve("registry-module")
        with client.download(release) as downloaded:
            observed = downloaded.path
    assert observed is None
    assert not (tmp_path / "state").exists()


def test_registry_to_bundle_metadata_conflict_does_not_install(tmp_path: Path) -> None:
    bundle, _ = _bundle(tmp_path, "registry-module", backend=False)
    documents = _documents(bundle)
    metadata = _decoded(documents, "/modules/registry-module.json")
    metadata["versions"][0]["source_commit"] = "b" * 40
    _replace_json(documents, "/modules/registry-module.json", metadata)
    installer = _installer(tmp_path / "state")

    with _client(documents) as client:
        release = client.resolve("registry-module")
        with (
            client.download(release) as downloaded,
            staged_ocp_bundle(downloaded.path) as (package_root, package),
            pytest.raises(ModuleRegistryValidationError, match="source commit"),
        ):
            client.validate_bundle(release, package)
            installer.install(package_root)

    assert not installer.lock_path.exists()
    assert not installer.root.exists()


def test_download_is_bounded_and_temporary_file_is_removed(tmp_path: Path) -> None:
    bundle, _ = _bundle(tmp_path, "registry-module", backend=False)
    documents = _documents(bundle)
    with _client(documents) as resolver:
        release = resolver.resolve("registry-module")
    with (
        _client(documents, max_bundle_size=len(bundle.read_bytes()) - 1) as client,
        pytest.raises(ModuleRegistryHTTPError, match="size limit"),
        client.download(release),
    ):
        pass

    with _client(documents) as client:
        with client.download(release) as downloaded:
            temporary = downloaded.path
            assert temporary.is_file()
        assert not temporary.exists()


def test_incomplete_content_length_is_rejected(tmp_path: Path) -> None:
    bundle, _ = _bundle(tmp_path, "registry-module", backend=False)
    documents = _documents(bundle)
    artifact_path = "/modules/registry-module/1.0.0/registry-module-1.0.0.ocp"
    headers = {artifact_path: {"content-length": str(len(documents[artifact_path]) + 10)}}
    with _client(documents) as resolver:
        release = resolver.resolve("registry-module")
    with (
        _client(documents, headers=headers) as client,
        pytest.raises(ModuleRegistryHTTPError, match="incomplete"),
        client.download(release),
    ):
        pass


def test_http_error_timeout_redirect_limit_and_unsafe_redirect(tmp_path: Path) -> None:
    _bundle(tmp_path, "registry-module", backend=False)

    def failure(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    with (
        ModuleRegistryClient(BASE_URL, transport=httpx.MockTransport(failure)) as client,
        pytest.raises(ModuleRegistryHTTPError, match="HTTP 503"),
    ):
        client.resolve("registry-module")

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("controlled", request=request)

    with (
        ModuleRegistryClient(BASE_URL, transport=httpx.MockTransport(timeout)) as client,
        pytest.raises(ModuleRegistryHTTPError, match="timed out"),
    ):
        client.resolve("registry-module")

    def redirect(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "/index.json"}, request=request)

    with (
        ModuleRegistryClient(
            BASE_URL,
            transport=httpx.MockTransport(redirect),
            max_redirects=1,
        ) as client,
        pytest.raises(ModuleRegistryHTTPError, match="redirect limit"),
    ):
        client.resolve("registry-module")

    def unsafe_redirect(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"location": "http://registry.test/index.json"},
            request=request,
        )

    with (
        ModuleRegistryClient(
            BASE_URL,
            transport=httpx.MockTransport(unsafe_redirect),
        ) as client,
        pytest.raises(ModuleRegistryValidationError, match="HTTPS"),
    ):
        client.resolve("registry-module")


def test_installed_module_inventory_needs_no_registry(tmp_path: Path) -> None:
    bundle, _ = _bundle(tmp_path, "registry-module", backend=False)
    documents = _documents(bundle)
    with _client(documents) as client:
        _, entry, installer = _install_from_client(client, tmp_path / "state")

    assert read_modules_lock(installer.lock_path).modules == (entry,)
    assert installer.inventory().modules[-1].id == "registry-module"
