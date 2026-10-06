import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

_password_hasher = PasswordHasher()
# Verified when no account exists so login timing does not reveal that fact.
_DUMMY_PASSWORD_HASH = _password_hasher.hash("not-a-real-account")


def hash_password(password: str) -> str:
    """Hash a password with Argon2id. The plaintext is not retained."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return whether the password matches the stored hash."""
    if password_hash.startswith("$argon2"):
        try:
            return _password_hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
    if password_hash.startswith("pbkdf2_sha256$"):
        return hmac.compare_digest(password_hash, _legacy_seed_hash(password))
    _password_hasher.verify(_DUMMY_PASSWORD_HASH, "not-a-real-account")
    return False


def password_needs_rehash(password_hash: str) -> bool:
    if not password_hash.startswith("$argon2"):
        return False
    return _password_hasher.check_needs_rehash(password_hash)


def dummy_password_check(password: str) -> None:
    """Spend Argon2 time when the account does not exist."""
    verify_password(password, _DUMMY_PASSWORD_HASH)


def generate_secret() -> str:
    """Return a URL-safe random secret. Callers store only a hash of it."""
    return secrets.token_urlsafe(32)


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _legacy_seed_hash(password: str) -> str:
    """Match the original development seed hash. New passwords use Argon2."""
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        b"stocksense-dev-seed",
        100_000,
    )
    return f"pbkdf2_sha256$stocksense-dev-seed${digest.hex()}"
