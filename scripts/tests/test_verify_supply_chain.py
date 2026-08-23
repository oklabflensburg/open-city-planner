from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "verify_supply_chain", REPOSITORY / "scripts/verify-supply-chain.py"
)
assert SPEC and SPEC.loader
VERIFY_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY_MODULE)


class SupplyChainPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for relative in (".github/workflows", "backend", "deploy/ansible", "frontend"):
            source = REPOSITORY / relative
            destination = self.root / relative
            if relative == "backend":
                destination.mkdir(parents=True)
                shutil.copy2(source / "pyproject.toml", destination)
                shutil.copy2(source / "uv.lock", destination)
            elif relative == "frontend":
                destination.mkdir(parents=True)
                shutil.copy2(source / "package.json", destination)
            else:
                shutil.copytree(source, destination)
        shutil.copy2(REPOSITORY / ".python-version", self.root)
        shutil.copy2(REPOSITORY / ".node-version", self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def verify(self, *, check_lock: bool = False) -> list[str]:
        return VERIFY_MODULE.verify(self.root, check_lock=check_lock)

    def test_current_repository_policy_passes(self) -> None:
        self.assertEqual(self.verify(), [])

    def test_action_major_tag_is_rejected(self) -> None:
        workflow = self.root / ".github/workflows/backend.yml"
        workflow.write_text(workflow.read_text().replace(
            "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803",
            "actions/checkout@v6",
            1,
        ))
        self.assertTrue(any("not pinned to a full SHA" in error for error in self.verify()))

    def test_undigested_postgis_image_is_rejected(self) -> None:
        workflow = self.root / ".github/workflows/backend.yml"
        workflow.write_text(workflow.read_text().replace(
            "postgis/postgis:16-3.5@sha256:19b6ffa248d2f864d29d6c338459f02d63c0d7ce341fa86b3bcba8484a130bff",
            "postgis/postgis:16-3.5",
            1,
        ))
        self.assertTrue(any("not pinned by SHA-256" in error for error in self.verify()))

    def test_ansible_version_range_is_rejected(self) -> None:
        requirements = self.root / "deploy/ansible/requirements.txt"
        requirements.write_text("ansible-core>=2.17,<2.20\n")
        errors = self.verify()
        self.assertTrue(any("must be pinned" in error for error in errors))

    def test_stale_uv_lock_is_rejected(self) -> None:
        pyproject = self.root / "backend/pyproject.toml"
        pyproject.write_text(pyproject.read_text().replace(
            '"alembic>=1.16.4"', '"alembic>=1.17.0"', 1
        ))
        self.assertTrue(any("uv.lock is stale" in error for error in self.verify(check_lock=True)))


if __name__ == "__main__":
    unittest.main()
