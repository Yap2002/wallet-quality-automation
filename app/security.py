import hashlib
import secrets


def generate_api_key() -> str:
    """Generate a high-entropy credential that is shown only when created."""
    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """Store a one-way representation instead of the plaintext credential."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()
