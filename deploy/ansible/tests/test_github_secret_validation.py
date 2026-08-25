import importlib.util
import os
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "deploy/ansible/scripts/build-github-vars.py"
SPEC = importlib.util.spec_from_file_location("build_github_vars", SCRIPT)
assert SPEC and SPEC.loader
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class GitHubSecretValidationTest(unittest.TestCase):
    def test_quoted_escapes_carriage_returns_and_newlines(self) -> None:
        self.assertEqual(BUILDER.quoted("token\r\nvalue"), '"token\\r\\nvalue"')

    def test_rejects_secret_with_trailing_carriage_return(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"STADTPLANER_MASTODON_ACCESS_TOKEN": "token-value\r"},
            clear=False,
        ):
            with self.assertRaisesRegex(
                SystemExit,
                "STADTPLANER_MASTODON_ACCESS_TOKEN",
            ):
                BUILDER.validate_secret_values()

    def test_rejects_multiline_secret(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"STADTPLANER_GROQ_API_KEY": "first-line\nsecond-line"},
            clear=False,
        ):
            with self.assertRaisesRegex(SystemExit, "STADTPLANER_GROQ_API_KEY"):
                BUILDER.validate_secret_values()

    def test_accepts_single_line_secret(self) -> None:
        clean_environment = {name: "single-line-value" for name in BUILDER.SECRET_KEYS}
        with mock.patch.dict(os.environ, clean_environment, clear=True):
            BUILDER.validate_secret_values()


if __name__ == "__main__":
    unittest.main()
