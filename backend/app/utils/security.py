import base64
import hashlib

from cryptography.fernet import Fernet


def _fernet(secret_key: str) -> Fernet:
    # derive a valid 32-byte fernet key from whatever string the secret_key is
    key = hashlib.sha256(secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_token(token: str, secret_key: str) -> str:
    """encrypt an oauth token before saving it to the database."""
    return _fernet(secret_key).encrypt(token.encode()).decode()


def decrypt_token(encrypted: str, secret_key: str) -> str:
    """decrypt a token retrieved from the database."""
    return _fernet(secret_key).decrypt(encrypted.encode()).decode()
