import hashlib
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import Classification
from app.core.permissions import can_access_document, get_allowed_classifications
from app.models.document import Document
from app.models.pii_finding import PiiFinding
from app.models.user import User


class DocumentService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save_upload(
        self,
        file: UploadFile,
        user: User,
        classification: str = "internal",
    ) -> Document:
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=422, detail="Only PDF files are accepted.")
        if classification not in [c.value for c in Classification]:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid classification. Must be one of: {[c.value for c in Classification]}",
            )

        upload_dir = Path(settings.UPLOAD_DIR) / str(user.tenant_id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        stored_filename = f"{uuid.uuid4()}.pdf"
        file_path = upload_dir / stored_filename

        sha256 = hashlib.sha256()
        with open(file_path, "wb") as f:
            while chunk := file.file.read(65536):
                sha256.update(chunk)
                f.write(chunk)

        doc = Document(
            tenant_id=user.tenant_id,
            uploaded_by_id=user.id,
            filename=stored_filename,
            original_filename=file.filename or stored_filename,
            content_type=file.content_type,
            file_path=str(file_path),
            checksum=sha256.hexdigest(),
            status="uploaded",
            classification=classification,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def get_documents(self, tenant_id: uuid.UUID, user: User) -> list[Document]:
        """Return documents the user is allowed to see based on their role."""
        allowed = get_allowed_classifications(user)
        return (
            self.db.query(Document)
            .filter(
                Document.tenant_id == tenant_id,
                Document.classification.in_(allowed),
            )
            .order_by(Document.created_at.desc())
            .all()
        )

    def get_document(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user: User,
    ) -> Document:
        doc = (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.tenant_id == tenant_id)
            .first()
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
        if not can_access_document(user, doc):
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to access this document.",
            )
        return doc

    def update_classification(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
        classification: str,
    ) -> Document:
        if classification not in [c.value for c in Classification]:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid classification. Must be one of: {[c.value for c in Classification]}",
            )
        doc = (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.tenant_id == tenant_id)
            .first()
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
        doc.classification = classification
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def delete_document(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> None:
        """Delete document, its chunks, PII findings, Qdrant vectors, and the file."""
        doc = (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.tenant_id == tenant_id)
            .first()
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        # Remove from Qdrant first (external system — do before DB changes)
        from app.services.qdrant_service import qdrant_service

        try:
            qdrant_service.delete_by_document(str(document_id), str(tenant_id))
        except Exception:
            pass  # Log but don't block deletion if Qdrant is unreachable

        # Remove uploaded file
        file_path = Path(doc.file_path)
        if file_path.exists():
            file_path.unlink(missing_ok=True)

        # Cascade deletes chunks and PII findings via SQLAlchemy relationships
        self.db.delete(doc)
        self.db.commit()

    def get_pii_findings(self, document_id: uuid.UUID, tenant_id: uuid.UUID) -> list[PiiFinding]:
        # Validate document belongs to tenant
        doc = (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.tenant_id == tenant_id)
            .first()
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
        return (
            self.db.query(PiiFinding)
            .filter(PiiFinding.document_id == document_id)
            .order_by(PiiFinding.created_at.asc())
            .all()
        )

    def pii_findings_count(self, document_id: uuid.UUID) -> int:
        return (
            self.db.query(PiiFinding)
            .filter(PiiFinding.document_id == document_id)
            .count()
        )
