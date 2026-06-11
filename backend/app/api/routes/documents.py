import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_user
from app.core.enums import UserRole
from app.core.permissions import (
    require_classification_update_permission,
    require_pii_view_permission,
    require_tenant_admin,
    require_upload_permission,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.document import (
    DocumentClassificationUpdate,
    DocumentResponse,
    DocumentUploadResponse,
)
from app.schemas.pii import PiiFindingResponse
from app.services.audit_service import AuditService
from app.services.document_service import DocumentService
from app.workers.tasks import process_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=202)
def upload_document(
    file: UploadFile = File(...),
    classification: str = Form(default="internal"),
    db: Session = Depends(get_db),
    user: User = Depends(require_upload_permission()),
) -> DocumentUploadResponse:
    doc = DocumentService(db).save_upload(file, user, classification=classification)

    AuditService(db).log(
        event_type="document.uploaded",
        user_id=user.id,
        tenant_id=user.tenant_id,
        entity_type="document",
        entity_id=str(doc.id),
        metadata={
            "filename": doc.original_filename,
            "checksum": doc.checksum,
            "classification": doc.classification,
        },
    )

    process_document.delay(str(doc.id))

    return DocumentUploadResponse(
        id=doc.id,
        status=doc.status,
        message="Document uploaded and queued for processing.",
    )


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    db: Session = Depends(get_db),
    user: User = Depends(get_tenant_user),
) -> list[DocumentResponse]:
    docs = DocumentService(db).get_documents(user.tenant_id, user)

    # Attach PII count for privileged roles
    privileged = UserRole(user.role) in {UserRole.TENANT_ADMIN, UserRole.COMPLIANCE_OFFICER}
    svc = DocumentService(db)
    result = []
    for doc in docs:
        response = DocumentResponse.model_validate(doc)
        if privileged:
            response.pii_findings_count = svc.pii_findings_count(doc.id)
        result.append(response)
    return result


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_tenant_user),
) -> DocumentResponse:
    doc = DocumentService(db).get_document(document_id, user.tenant_id, user)
    response = DocumentResponse.model_validate(doc)

    if UserRole(user.role) in {UserRole.TENANT_ADMIN, UserRole.COMPLIANCE_OFFICER}:
        response.pii_findings_count = DocumentService(db).pii_findings_count(doc.id)
    return response


@router.patch("/{document_id}/classification", response_model=DocumentResponse)
def update_classification(
    document_id: uuid.UUID,
    body: DocumentClassificationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_classification_update_permission()),
) -> DocumentResponse:
    old_doc = DocumentService(db).get_document(document_id, user.tenant_id, user)
    old_classification = old_doc.classification

    doc = DocumentService(db).update_classification(document_id, user.tenant_id, body.classification)

    AuditService(db).log(
        event_type="document.classification_updated",
        user_id=user.id,
        tenant_id=user.tenant_id,
        entity_type="document",
        entity_id=str(doc.id),
        metadata={
            "filename": doc.original_filename,
            "old_classification": old_classification,
            "new_classification": doc.classification,
        },
    )
    return DocumentResponse.model_validate(doc)


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_tenant_admin()),
) -> None:
    # Capture filename before deletion for audit log
    doc = DocumentService(db).get_document(document_id, user.tenant_id, user)
    filename = doc.original_filename

    DocumentService(db).delete_document(document_id, user.tenant_id)

    AuditService(db).log(
        event_type="document.deleted",
        user_id=user.id,
        tenant_id=user.tenant_id,
        entity_type="document",
        entity_id=str(document_id),
        metadata={"filename": filename},
    )


@router.post("/{document_id}/reindex", status_code=202)
def reindex_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_classification_update_permission()),
) -> dict:
    doc = DocumentService(db).get_document(document_id, user.tenant_id, user)

    doc.status = "uploaded"  # reset so the task can pick it up cleanly
    db.commit()

    AuditService(db).log(
        event_type="document.reindex_requested",
        user_id=user.id,
        tenant_id=user.tenant_id,
        entity_type="document",
        entity_id=str(document_id),
        metadata={"filename": doc.original_filename},
    )

    process_document.delay(str(document_id))
    return {"message": "Reindex task enqueued.", "document_id": str(document_id)}


@router.get("/{document_id}/pii-findings", response_model=list[PiiFindingResponse])
def list_pii_findings(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_pii_view_permission()),
) -> list[PiiFindingResponse]:
    return DocumentService(db).get_pii_findings(document_id, user.tenant_id)
