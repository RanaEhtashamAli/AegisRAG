from enum import StrEnum


class UserRole(StrEnum):
    TENANT_ADMIN = "tenant_admin"
    COMPLIANCE_OFFICER = "compliance_officer"
    ANALYST = "analyst"
    VIEWER = "viewer"


class Classification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"
