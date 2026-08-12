from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()


def validate_password_policy(password: str) -> None:
    if len(password) < 12:
        raise ValueError("Das Passwort muss mindestens 12 Zeichen lang sein.")


def hash_password(password: str) -> str:
    validate_password_policy(password)
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)
