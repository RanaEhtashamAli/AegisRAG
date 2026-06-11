import hashlib
import re
from dataclasses import dataclass


@dataclass
class PiiMatch:
    pii_type: str
    raw_value: str
    masked_preview: str


# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

_PHONE_RE = re.compile(
    r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)

# US SSN: 3-2-4 digit pattern, excludes obviously invalid values
_SSN_RE = re.compile(
    r"\b(?!000|666|9\d{2})\d{3}[-\s](?!00)\d{2}[-\s](?!0000)\d{4}\b"
)

# Generic 16-digit credit card (groups of 4, separated by space or dash)
_CREDIT_CARD_RE = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")

# IBAN: 2-letter country code, 2 check digits, then up to 30 alphanumeric
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}[A-Z0-9]{0,16}\b")


# ---------------------------------------------------------------------------
# Masking helpers
# ---------------------------------------------------------------------------


def _mask_email(value: str) -> str:
    parts = value.split("@")
    if len(parts) != 2:
        return "***@***"
    local = parts[0]
    masked = (local[:2] + "***") if len(local) > 2 else "***"
    return f"{masked}@{parts[1]}"


def _mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return ("*" * max(len(digits) - 4, 0)) + digits[-4:] if len(digits) >= 4 else "****"


def _mask_ssn(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return f"***-**-{digits[-4:]}" if len(digits) >= 4 else "***-**-****"


def _mask_card(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return f"**** **** **** {digits[-4:]}" if len(digits) >= 4 else "**** **** **** ****"


def _mask_iban(value: str) -> str:
    clean = value.replace(" ", "")
    return f"{clean[:4]}****{clean[-4:]}" if len(clean) >= 8 else f"{clean[:4]}****"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_pii(text: str) -> list[PiiMatch]:
    """Scan *text* for PII patterns. Returns matches with masked previews."""
    matches: list[PiiMatch] = []

    for m in _EMAIL_RE.finditer(text):
        matches.append(PiiMatch("email", m.group(), _mask_email(m.group())))

    for m in _PHONE_RE.finditer(text):
        matches.append(PiiMatch("phone", m.group(), _mask_phone(m.group())))

    for m in _SSN_RE.finditer(text):
        matches.append(PiiMatch("ssn", m.group(), _mask_ssn(m.group())))

    for m in _CREDIT_CARD_RE.finditer(text):
        # Skip SSN false-positives already matched above
        raw = m.group()
        if not _SSN_RE.match(raw):
            matches.append(PiiMatch("credit_card", raw, _mask_card(raw)))

    for m in _IBAN_RE.finditer(text):
        matches.append(PiiMatch("iban", m.group(), _mask_iban(m.group())))

    return matches


def hash_raw_value(raw: str) -> str:
    """SHA-256 of the raw matched string. Raw value is never persisted."""
    return hashlib.sha256(raw.encode()).hexdigest()
