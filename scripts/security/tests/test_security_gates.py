from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.security.audit_frontend import blocking_advisories
from scripts.security.enforce_sarif import blocking_findings
from scripts.security.security_exceptions import ExceptionPolicyError, load_exceptions


class SecurityExceptionTests(unittest.TestCase):
    def write_policy(self, content: str) -> Path:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as temporary:
            temporary.write(content)
        path = Path(temporary.name)
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def test_empty_policy_is_valid(self) -> None:
        path = self.write_policy("version: 1\nexceptions: []\n")
        self.assertEqual(load_exceptions(path, today=date(2026, 8, 23)), [])

    def test_expired_exception_is_rejected(self) -> None:
        path = self.write_policy(
            """version: 1
exceptions:
  - id: CVE-2099-0001
    scanner: backend-dependency
    reason: Temporary compatibility constraint
    owner: security-team
    expires: '2026-08-22'
    mitigation: Network access is restricted
    review_date: '2026-08-20'
"""
        )
        with self.assertRaisesRegex(ExceptionPolicyError, "expired"):
            load_exceptions(path, today=date(2026, 8, 23))

    def test_duplicate_ids_are_rejected(self) -> None:
        entry = """  - id: TEST-1
    scanner: codeql
    reason: Temporary false positive
    owner: security-team
    expires: '2026-09-30'
    mitigation: Input is validated before this path
    review_date: '2026-09-01'
"""
        path = self.write_policy("version: 1\nexceptions:\n" + entry + entry)
        with self.assertRaisesRegex(ExceptionPolicyError, "duplicate"):
            load_exceptions(path, today=date(2026, 8, 23))


class GatePolicyTests(unittest.TestCase):
    def test_high_codeql_finding_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "result.sarif"
            report.write_text(json.dumps({
                "runs": [{
                    "tool": {"driver": {"rules": [{
                        "id": "py/test-rule",
                        "properties": {"security-severity": "8.1"},
                    }]}},
                    "results": [{"ruleId": "py/test-rule", "level": "warning"}],
                }]
            }))
            self.assertEqual(blocking_findings([report], set()), [("py/test-rule", "high")])
            self.assertEqual(blocking_findings([report], {"py/test-rule"}), [])

    def test_secret_sarif_finding_blocks_by_unique_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "secret.sarif"
            report.write_text(json.dumps({
                "runs": [{
                    "tool": {"driver": {"rules": [{"id": "fixture-secret"}]}},
                    "results": [{
                        "ruleId": "fixture-secret",
                        "partialFingerprints": {"commitSha": "abc123"},
                        "locations": [{"physicalLocation": {
                            "artifactLocation": {"uri": "fixture.txt"},
                            "region": {"startLine": 7},
                        }}],
                    }],
                }]
            }))
            finding_id = "fixture-secret@abc123:fixture.txt:7"
            self.assertEqual(
                blocking_findings([report], set(), scanner="secret-scan"),
                [(finding_id, "high")],
            )
            self.assertEqual(
                blocking_findings([report], {finding_id}, scanner="secret-scan"),
                [],
            )

    def test_high_frontend_advisory_blocks(self) -> None:
        document = {"advisories": {"123": {
            "id": 123,
            "github_advisory_id": "GHSA-AAAA-BBBB-CCCC",
            "module_name": "fixture-only-package",
            "severity": "high",
        }}}
        self.assertEqual(
            blocking_advisories(document, set()),
            [("GHSA-AAAA-BBBB-CCCC", "fixture-only-package", "high")],
        )
        self.assertEqual(blocking_advisories(document, {"GHSA-AAAA-BBBB-CCCC"}), [])


if __name__ == "__main__":
    unittest.main()
