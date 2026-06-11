import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.enums import UserRole
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.tenant import TenantCreate


class TenantService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_tenant(self, data: TenantCreate, user: User) -> Tenant:
        if user.tenant_id:
            raise HTTPException(status_code=400, detail="User already belongs to a tenant.")
        if self.db.query(Tenant).filter(Tenant.slug == data.slug).first():
            raise HTTPException(status_code=409, detail="Tenant slug already taken.")

        tenant = Tenant(name=data.name, slug=data.slug)
        self.db.add(tenant)
        self.db.flush()  # populate tenant.id before referencing it

        # Creator becomes the first tenant admin
        user.tenant_id = tenant.id
        user.role = UserRole.TENANT_ADMIN.value
        self.db.commit()
        self.db.refresh(tenant)
        return tenant

    def get_tenant(self, tenant_id: uuid.UUID) -> Tenant:
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found.")
        return tenant
