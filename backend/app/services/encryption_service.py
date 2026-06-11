"""Field-level encryption service using Fernet (AES-128-CBC + HMAC-SHA256).

Architecture notes:
- FIELD_ENCRYPTION_KEY must be a URL-safe base64-encoded 32-byte key.
  Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
- Key rotation: re-encrypt fields with the new key, then retire the old key.
  A full envelope encryption design (DEK + KEK via Vault) is the production path;
  this service is the application layer that would wrap that pattern.
- If FIELD_ENCRYPTION_KEY is empty, the service passes values through unchanged
  so existing deployments are not broken.

Limitation (documented honestly):
- Fernet is symmetric — the same key encrypts and decrypts. Key compromise
  means all stored ciphertext is exposed. Use Vault/KMS for key management
  in production.
- At-rest disk encryption (PostgreSQL volume, MinIO) is a separate layer
  handled at the infrastructure level (see docs/security-hardening.md).
"""
from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_fernet = None
_initialized = False


def _get_fernet():
    global _fernet, _initialized
    if _initialized:
        return _fernet
    _initialized = True
    if not settings.FIELD_ENCRYPTION_KEY:
        logger.info("field_encryption_disabled: FIELD_ENCRYPTION_KEY not set")
        return None
    try:
        from cryptography.fernet import Fernet
        _fernet = Fernet(settings.FIELD_ENCRYPTION_KEY.encode())
        logger.info("field_encryption_enabled")
    except Exception as exc:
        logger.error("field_encryption_init_failed: %s", exc)
        _fernet = None
    return _fernet


class EncryptionService:
    """Encrypt and decrypt string field values."""

    def encrypt(self, plaintext: str) -> str:
        """Return encrypted ciphertext (base64 string). Returns plaintext if key not set."""
        f = _get_fernet()
        if f is None:
            return plaintext
        return f.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Return decrypted plaintext. Returns ciphertext unchanged if key not set."""
        f = _get_fernet()
        if f is None:
            return ciphertext
        try:
            return f.decrypt(ciphertext.encode()).decode()
        except Exception as exc:
            logger.error("field_decryption_failed: %s", exc)
            return ciphertext

    def is_enabled(self) -> bool:
        return _get_fernet() is not None

    def rotate_hint(self) -> str:
        """Return a hint for key rotation — not an automated process."""
        return (
            "To rotate: (1) generate new key, (2) re-encrypt all encrypted fields "
            "using both old and new key, (3) update FIELD_ENCRYPTION_KEY, "
            "(4) retire old key. Consider HashiCorp Vault for automated rotation."
        )


encryption_service = EncryptionService()
