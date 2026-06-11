from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.tenant import TenantCreate, TenantResponse
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantService

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantResponse, status_code=201)
def create_tenant(
    data: TenantCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TenantResponse:
    tenant = TenantService(db).create_tenant(data, user)
    AuditService(db).log(
        event_type="tenant.created",
        user_id=user.id,
        tenant_id=tenant.id,
        entity_type="tenant",
        entity_id=str(tenant.id),
        metadata={"name": tenant.name, "slug": tenant.slug},
    )
    return tenant


@router.get("/me", response_model=TenantResponse)
def get_my_tenant(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TenantResponse:
    if not user.tenant_id:
        raise HTTPException(status_code=404, detail="User does not belong to a tenant.")
    return TenantService(db).get_tenant(user.tenant_id)
