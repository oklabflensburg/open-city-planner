import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/validate_webp.py"
SPEC = importlib.util.spec_from_file_location("validate_webp", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def webp_bytes(payload: bytes) -> bytes:
    body = b"WEBP" + payload
    return b"RIFF" + len(body).to_bytes(4, "little") + body


class ValidateWebpTest(unittest.TestCase):
    def test_accepts_non_utf8_webp_bytes(self) -> None:
        image = webp_bytes(b"VP8 " + b"\xff\xfe\x80\x00" * 20)
        MODULE.validate_webp(image, minimum_size=64)

    def test_rejects_invalid_riff_header(self) -> None:
        image = b"FAIL" + webp_bytes(b"x" * 80)[4:]
        with self.assertRaisesRegex(ValueError, "RIFF header"):
            MODULE.validate_webp(image, minimum_size=64)

    def test_rejects_invalid_webp_signature(self) -> None:
        image = bytearray(webp_bytes(b"x" * 80))
        image[8:12] = b"NOPE"
        with self.assertRaisesRegex(ValueError, "WEBP signature"):
            MODULE.validate_webp(bytes(image), minimum_size=64)

    def test_rejects_truncated_riff_payload(self) -> None:
        image = webp_bytes(b"x" * 80)[:-1]
        with self.assertRaisesRegex(ValueError, "size mismatch"):
            MODULE.validate_webp(image, minimum_size=64)


if __name__ == "__main__":
    unittest.main()
