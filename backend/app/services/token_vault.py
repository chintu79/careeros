"""
Token Vault for CareerOS Integration Credentials.
Provides authenticated encryption at rest using Fernet with MultiFernet key-rotation support.
Guarantees zero plaintext tokens in logs, exception traces, or API responses.
"""
import os
import base64
import hashlib
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from backend.app.config import settings

logger = logging.getLogger(__name__)


def derive_fernet_key(secret: str) -> bytes:
    """Derives a deterministic, 32-byte URL-safe base64 Fernet key from any secret string."""
    if not secret:
        raise ValueError("Cannot derive Fernet key from empty secret")
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_token_vault_fernet() -> MultiFernet:
    """
    Initializes a MultiFernet instance with the primary secret and any rotation secrets.
    The first key is used for all new encryptions.
    Any key in the keyring can decrypt existing ciphertexts.
    """
    primary_secret = os.getenv("CAREEROS_TOKEN_SECRET", getattr(settings, "CAREEROS_TOKEN_SECRET", None))
    
    if settings.is_production:
        if not primary_secret or len(primary_secret.strip()) < 32 or primary_secret in ("careeros-secure-vault-seed", "changeme"):
            raise RuntimeError(
                "FATAL SECURITY MISCONFIGURATION: Production requires a secure CAREEROS_TOKEN_SECRET "
                "with at least 32 characters. Token vault cannot initialize."
            )
    else:
        if not primary_secret:
            primary_secret = settings.SECRET_KEY or "careeros-development-vault-seed-2026"

    keys: List[Fernet] = [Fernet(derive_fernet_key(primary_secret))]

    # Add optional rotation fallback secrets (comma-separated older secrets)
    rotation_secrets = os.getenv("CAREEROS_ROTATION_SECRETS", "")
    if rotation_secrets:
        for r_sec in rotation_secrets.split(","):
            r_sec = r_sec.strip()
            if r_sec:
                try:
                    keys.append(Fernet(derive_fernet_key(r_sec)))
                except Exception as e:
                    logger.warning(f"Failed to load rotation key: {e}")

    return MultiFernet(keys)


def encrypt_token(plain_token: str) -> str:
    """
    Encrypts a sensitive OAuth or Personal Access Token at rest using the primary vault key.
    Returns URL-safe base64-encoded ciphertext.
    Never stores or falls back to plaintext.
    """
    if not plain_token:
        return ""
    clean = plain_token.strip()
    try:
        vault = get_token_vault_fernet()
        cipher_bytes = vault.encrypt(clean.encode("utf-8"))
        return cipher_bytes.decode("utf-8")
    except Exception as e:
        logger.error("Token encryption failed (details omitted for security)")
        raise ValueError("Failed to securely encrypt token") from e


def decrypt_token(cipher_token: str) -> str:
    """
    Decrypts a ciphertext token at runtime using the active keyring.
    Never logs plaintext tokens or ciphertexts.
    """
    if not cipher_token:
        return ""
    clean = cipher_token.strip()
    try:
        vault = get_token_vault_fernet()
        plain_bytes = vault.decrypt(clean.encode("utf-8"))
        return plain_bytes.decode("utf-8")
    except InvalidToken as e:
        logger.error("Token decryption failed: invalid ciphertext or secret mismatch")
        raise ValueError("Failed to decrypt token: authentication tag verification failed") from e
    except Exception as e:
        logger.error("Token decryption failed due to unexpected error")
        raise ValueError("Failed to decrypt token") from e


def rotate_token_ciphertext(cipher_token: str) -> str:
    """
    Re-encrypts a token under the current primary key using MultiFernet.rotate().
    Allows zero-downtime key rotation: older tokens can be lazily or batch-rotated.
    """
    if not cipher_token:
        return ""
    clean = cipher_token.strip()
    try:
        vault = get_token_vault_fernet()
        rotated_bytes = vault.rotate(clean.encode("utf-8"))
        return rotated_bytes.decode("utf-8")
    except Exception as e:
        logger.error("Token rotation failed")
        raise ValueError("Failed to rotate token ciphertext") from e


def rotate_all_stored_tokens(db) -> Dict[str, int]:
    """
    Operational helper: batch re-encrypts all stored IntegrationConnection tokens
    to the current primary vault key using MultiFernet.rotate().
    Preserves original ciphertext for any connection where rotation fails.
    """
    from backend.app.models.integration import IntegrationConnection
    conns = db.query(IntegrationConnection).filter(IntegrationConnection.encrypted_access_token.isnot(None)).all()
    rotated = 0
    failed = 0
    for conn in conns:
        if conn.encrypted_access_token:
            orig = conn.encrypted_access_token
            try:
                new_cipher = rotate_token_ciphertext(orig)
                if new_cipher != orig:
                    conn.encrypted_access_token = new_cipher
                    conn.updated_at = datetime.utcnow()
                    rotated += 1
            except Exception as e:
                logger.error(f"Failed to rotate token for connection {conn.id}: {e}")
                conn.encrypted_access_token = orig
                failed += 1
    if rotated > 0:
        db.commit()
    return {"total": len(conns), "rotated": rotated, "failed": failed}
