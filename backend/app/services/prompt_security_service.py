from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.prompt_security_event import PromptSecurityEvent

_INJECTION_KEYWORDS = [
    "ignore previous instructions",
    "ignore all previous",
    "disregard previous",
    "forget everything",
    "you are now",
    "act as",
    "pretend you are",
    "new persona",
    "jailbreak",
    "dan mode",
    "do anything now",
    "override safety",
    "bypass restrictions",
    "ignore your system prompt",
    "ignore the context",
    "reveal your system prompt",
    "print your instructions",
]

_INJECTION_PATTERNS = [
    re.compile(r"```\s*system", re.IGNORECASE),
    re.compile(r"<\s*system\s*>", re.IGNORECASE),
    re.compile(r"\[INST\].*override", re.IGNORECASE | re.DOTALL),
    re.compile(r"###\s*instruction", re.IGNORECASE),
]


@dataclass
class SecurityCheckResult:
    is_safe: bool
    risk_level: str  # "low" | "medium" | "high"
    detection_type: str | None
    matched_pattern: str | None


class PromptSecurityService:
    def check(self, text: str) -> SecurityCheckResult:
        lower = text.lower()

        for kw in _INJECTION_KEYWORDS:
            if kw in lower:
                return SecurityCheckResult(
                    is_safe=False,
                    risk_level="high",
                    detection_type="keyword",
                    matched_pattern=kw,
                )

        for pat in _INJECTION_PATTERNS:
            m = pat.search(text)
            if m:
                return SecurityCheckResult(
                    is_safe=False,
                    risk_level="high",
                    detection_type="pattern",
                    matched_pattern=pat.pattern,
                )

        if len(text) > 2000 and text.count(" ") < 10:
            return SecurityCheckResult(
                is_safe=False,
                risk_level="medium",
                detection_type="heuristic",
                matched_pattern="long_no_spaces",
            )

        return SecurityCheckResult(
            is_safe=True, risk_level="low", detection_type=None, matched_pattern=None
        )

    def log_event(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        input_text: str,
        result: SecurityCheckResult,
        action_taken: str,
    ) -> None:
        event = PromptSecurityEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            input_text=input_text[:1000],
            detection_type=result.detection_type or "none",
            matched_pattern=result.matched_pattern,
            risk_level=result.risk_level,
            action_taken=action_taken,
        )
        db.add(event)
        db.commit()


prompt_security_service = PromptSecurityService()
