"""Unit tests for field-level encryption service."""
import pytest
from cryptography.fernet import Fernet

from app.services.encryption_service import EncryptionService


def _make_svc(key: str | None = None) -> EncryptionService:
    """Create a fresh EncryptionService with an optional Fernet key."""
    from unittest.mock import patch

    svc = EncryptionService()
    # Reset the module-level cache so each test gets a fresh state
    import app.services.encryption_service as _mod
    _mod._fernet = None
    _mod._initialized = False

    if key is not None:
        with patch("app.services.encryption_service.settings") as s:
            s.FIELD_ENCRYPTION_KEY = key
            svc.encrypt("warmup")  # trigger init
    else:
        with patch("app.services.encryption_service.settings") as s:
            s.FIELD_ENCRYPTION_KEY = ""
            svc.encrypt("warmup")  # trigger init (no-op mode)
    return svc


# ── Disabled mode (no key) ────────────────────────────────────────────────────

def test_encrypt_passthrough_when_no_key():
    import app.services.encryption_service as _mod
    _mod._fernet = None
    _mod._initialized = False

    svc = EncryptionService()
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr("app.services.encryption_service.settings.FIELD_ENCRYPTION_KEY", "")
        _mod._initialized = False
        result = svc.encrypt("plaintext")
    assert result == "plaintext"


def test_decrypt_passthrough_when_no_key():
    import app.services.encryption_service as _mod
    _mod._fernet = None
    _mod._initialized = False

    svc = EncryptionService()
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr("app.services.encryption_service.settings.FIELD_ENCRYPTION_KEY", "")
        _mod._initialized = False
        result = svc.decrypt("ciphertext_or_plaintext")
    assert result == "ciphertext_or_plaintext"


def test_is_enabled_false_when_no_key(monkeypatch):
    import app.services.encryption_service as _mod
    _mod._fernet = None
    _mod._initialized = False
    monkeypatch.setattr("app.services.encryption_service.settings.FIELD_ENCRYPTION_KEY", "")
    svc = EncryptionService()
    assert svc.is_enabled() is False


# ── Enabled mode (with Fernet key) ───────────────────────────────────────────

@pytest.fixture
def fernet_key():
    return Fernet.generate_key().decode()


def test_encrypt_returns_different_from_plaintext(fernet_key, monkeypatch):
    import app.services.encryption_service as _mod
    _mod._fernet = None
    _mod._initialized = False
    monkeypatch.setattr(
        "app.services.encryption_service.settings.FIELD_ENCRYPTION_KEY", fernet_key
    )
    svc = EncryptionService()
    result = svc.encrypt("my secret value")
    assert result != "my secret value"
    assert len(result) > 0


def test_encrypt_decrypt_round_trip(fernet_key, monkeypatch):
    import app.services.encryption_service as _mod
    _mod._fernet = None
    _mod._initialized = False
    monkeypatch.setattr(
        "app.services.encryption_service.settings.FIELD_ENCRYPTION_KEY", fernet_key
    )
    svc = EncryptionService()
    plaintext = "sensitive personal data 12345"
    ciphertext = svc.encrypt(plaintext)
    recovered = svc.decrypt(ciphertext)
    assert recovered == plaintext


def test_encrypt_is_non_deterministic(fernet_key, monkeypatch):
    """Fernet uses a random IV — two encryptions of the same value differ."""
    import app.services.encryption_service as _mod
    _mod._fernet = None
    _mod._initialized = False
    monkeypatch.setattr(
        "app.services.encryption_service.settings.FIELD_ENCRYPTION_KEY", fernet_key
    )
    svc = EncryptionService()
    ct1 = svc.encrypt("hello")
    ct2 = svc.encrypt("hello")
    assert ct1 != ct2  # different IV each time


def test_decrypt_returns_ciphertext_on_invalid_token(fernet_key, monkeypatch):
    """Graceful degradation: bad ciphertext returns the input unchanged."""
    import app.services.encryption_service as _mod
    _mod._fernet = None
    _mod._initialized = False
    monkeypatch.setattr(
        "app.services.encryption_service.settings.FIELD_ENCRYPTION_KEY", fernet_key
    )
    svc = EncryptionService()
    bad = "not_a_valid_fernet_token"
    result = svc.decrypt(bad)
    assert result == bad  # returns input, does not raise


def test_is_enabled_true_with_valid_key(fernet_key, monkeypatch):
    import app.services.encryption_service as _mod
    _mod._fernet = None
    _mod._initialized = False
    monkeypatch.setattr(
        "app.services.encryption_service.settings.FIELD_ENCRYPTION_KEY", fernet_key
    )
    svc = EncryptionService()
    assert svc.is_enabled() is True


def test_rotate_hint_returns_string():
    svc = EncryptionService()
    hint = svc.rotate_hint()
    assert isinstance(hint, str)
    assert len(hint) > 10


def test_encrypt_empty_string(fernet_key, monkeypatch):
    import app.services.encryption_service as _mod
    _mod._fernet = None
    _mod._initialized = False
    monkeypatch.setattr(
        "app.services.encryption_service.settings.FIELD_ENCRYPTION_KEY", fernet_key
    )
    svc = EncryptionService()
    ct = svc.encrypt("")
    recovered = svc.decrypt(ct)
    assert recovered == ""
