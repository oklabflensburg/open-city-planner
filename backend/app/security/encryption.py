from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class MfaEncryptionError(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = get_settings().mfa_encryption_key
    if not key:
        raise MfaEncryptionError("MFA_ENCRYPTION_KEY is not configured")
    try:
        return Fernet(key.encode())
    except (TypeError, ValueError) as exc:
        raise MfaEncryptionError("MFA_ENCRYPTION_KEY is invalid") from exc


def encrypt_mfa_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_mfa_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise MfaEncryptionError("Stored MFA secret cannot be decrypted") from exc
