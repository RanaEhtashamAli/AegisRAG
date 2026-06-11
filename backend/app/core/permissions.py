from fastapi import Depends, HTTPException

from app.core.enums import Classification, UserRole

# Which classifications each role may access (without special conditions)
_ROLE_CLASSIFICATIONS: dict[UserRole, set[Classification]] = {
    UserRole.TENANT_ADMIN: {
        Classification.PUBLIC,
        Classification.INTERNAL,
        Classification.CONFIDENTIAL,
        Classification.RESTRICTED,
    },
    UserRole.COMPLIANCE_OFFICER: {
        Classification.PUBLIC,
        Classification.INTERNAL,
        Classification.CONFIDENTIAL,
        Classification.RESTRICTED,
    },
    UserRole.ANALYST: {
        Classification.PUBLIC,
        Classification.INTERNAL,
        Classification.CONFIDENTIAL,
    },
    UserRole.VIEWER: {
        Classification.PUBLIC,
        Classification.INTERNAL,
    },
}


def get_allowed_classifications(user) -> list[str]:
    """Return the list of classification strings the user may query via Qdrant."""
    role = UserRole(user.role)
    return [c.value for c in _ROLE_CLASSIFICATIONS.get(role, {Classification.PUBLIC})]


def can_access_document(user, document) -> bool:
    """Return True if the user may read the given document."""
    role = UserRole(user.role)
    classification = Classification(document.classification)
    allowed = _ROLE_CLASSIFICATIONS.get(role, set())

    return classification in allowed


def _require_roles(*roles: UserRole):
    """Return a FastAPI dependency that enforces at least one of the given roles."""

    def dep(user=Depends(_get_tenant_user_lazy())) -> object:
        if UserRole(user.role) not in roles:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to perform this action.",
            )
        return user

    return dep


def _get_tenant_user_lazy():
    """Deferred import to avoid circular dependency with deps.py."""

    def inner():
        from app.api.deps import get_tenant_user

        return get_tenant_user

    return inner()


# ---------------------------------------------------------------------------
# Convenience dependency factories — import these in route files
# ---------------------------------------------------------------------------


def require_tenant_admin():
    from app.api.deps import get_tenant_user

    def dep(user=Depends(get_tenant_user)):
        if UserRole(user.role) != UserRole.TENANT_ADMIN:
            raise HTTPException(
                status_code=403, detail="Only tenant admins can perform this action."
            )
        return user

    return dep


def require_upload_permission():
    from app.api.deps import get_tenant_user

    def dep(user=Depends(get_tenant_user)):
        if UserRole(user.role) not in {
            UserRole.TENANT_ADMIN,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.ANALYST,
        }:
            raise HTTPException(
                status_code=403, detail="Viewers cannot upload documents."
            )
        return user

    return dep


def require_audit_view_permission():
    from app.api.deps import get_tenant_user

    def dep(user=Depends(get_tenant_user)):
        if UserRole(user.role) not in {UserRole.TENANT_ADMIN, UserRole.COMPLIANCE_OFFICER}:
            raise HTTPException(
                status_code=403, detail="You do not have permission to view audit logs."
            )
        return user

    return dep


def require_classification_update_permission():
    from app.api.deps import get_tenant_user

    def dep(user=Depends(get_tenant_user)):
        if UserRole(user.role) not in {UserRole.TENANT_ADMIN, UserRole.COMPLIANCE_OFFICER}:
            raise HTTPException(
                status_code=403,
                detail="Only tenant admins and compliance officers may update document classification.",
            )
        return user

    return dep


def require_pii_view_permission():
    from app.api.deps import get_tenant_user

    def dep(user=Depends(get_tenant_user)):
        if UserRole(user.role) not in {UserRole.TENANT_ADMIN, UserRole.COMPLIANCE_OFFICER}:
            raise HTTPException(
                status_code=403, detail="You do not have permission to view PII findings."
            )
        return user

    return dep
