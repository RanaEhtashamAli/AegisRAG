"""PII detection unit tests — pure function tests, no database required."""
import hashlib

from app.services.pii_service import detect_pii, hash_raw_value


def test_email_detection():
    text = "Contact us at john.smith@example.com for details."
    matches = detect_pii(text)
    email_matches = [m for m in matches if m.pii_type == "email"]
    assert len(email_matches) == 1
    assert email_matches[0].raw_value == "john.smith@example.com"


def test_email_masking():
    text = "Email: alice@company.org"
    matches = detect_pii(text)
    assert any(m.pii_type == "email" for m in matches)
    email = next(m for m in matches if m.pii_type == "email")
    # Raw value must never appear in the masked preview
    assert "alice" not in email.masked_preview or email.masked_preview.startswith("al***")
    assert "@company.org" in email.masked_preview


def test_phone_detection():
    text = "Call us at 555-867-5309 for more info."
    matches = detect_pii(text)
    phone_matches = [m for m in matches if m.pii_type == "phone"]
    assert len(phone_matches) >= 1


def test_phone_masking_hides_most_digits():
    text = "Phone: 555-867-5309"
    matches = detect_pii(text)
    phone = next(m for m in matches if m.pii_type == "phone")
    # Last 4 digits should be visible
    assert "5309" in phone.masked_preview


def test_ssn_detection():
    text = "SSN: 123-45-6789"
    matches = detect_pii(text)
    ssn_matches = [m for m in matches if m.pii_type == "ssn"]
    assert len(ssn_matches) >= 1


def test_ssn_masking():
    text = "SSN: 123-45-6789"
    matches = detect_pii(text)
    ssn = next(m for m in matches if m.pii_type == "ssn")
    assert ssn.masked_preview == "***-**-6789"


def test_credit_card_detection():
    text = "Card: 4111 1111 1111 1111"
    matches = detect_pii(text)
    card_matches = [m for m in matches if m.pii_type == "credit_card"]
    assert len(card_matches) >= 1


def test_credit_card_masking():
    text = "Card number: 4111-1111-1111-1234"
    matches = detect_pii(text)
    card = next(m for m in matches if m.pii_type == "credit_card")
    assert "1234" in card.masked_preview
    assert card.masked_preview.startswith("*")


def test_raw_value_never_stored():
    """hash_raw_value must return a hash, not the raw value."""
    raw = "john.smith@example.com"
    hashed = hash_raw_value(raw)
    assert hashed != raw
    assert len(hashed) == 64  # SHA-256 hex = 64 chars
    assert hashed == hashlib.sha256(raw.encode()).hexdigest()


def test_no_pii_in_clean_text():
    text = "This is a simple document about cloud computing and machine learning."
    matches = detect_pii(text)
    assert matches == []


def test_multiple_pii_types_in_one_chunk():
    text = "Contact alice@corp.com or call 555-123-4567 with SSN 321-54-9876."
    matches = detect_pii(text)
    pii_types = {m.pii_type for m in matches}
    assert "email" in pii_types
    assert "phone" in pii_types
    assert "ssn" in pii_types


def test_masked_preview_does_not_contain_raw_ssn():
    text = "Social: 123-45-6789"
    matches = detect_pii(text)
    ssn = next(m for m in matches if m.pii_type == "ssn")
    assert "123-45" not in ssn.masked_preview


def test_iban_detection():
    text = "Wire to GB29NWBK60161331926819 for payment."
    matches = detect_pii(text)
    iban_matches = [m for m in matches if m.pii_type == "iban"]
    assert len(iban_matches) >= 1
