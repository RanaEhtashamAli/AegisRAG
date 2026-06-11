import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.permissions import require_tenant_admin
from app.db.session import get_db
from app.models.evaluation_run import EvaluationRun
from app.models.user import User

router = APIRouter(prefix="/evals", tags=["evals"])


class EvalRunResponse(BaseModel):
    id: uuid.UUID
    run_name: str
    status: str
    total_questions: int
    completed_questions: int
    faithfulness: float | None
    answer_relevancy: float | None
    context_recall: float | None
    context_precision: float | None
    error_message: str | None
    created_at: str
    completed_at: str | None

    model_config = {"from_attributes": True}


def _run_to_response(run: EvaluationRun) -> EvalRunResponse:
    return EvalRunResponse(
        id=run.id,
        run_name=run.run_name,
        status=run.status,
        total_questions=run.total_questions,
        completed_questions=run.completed_questions,
        faithfulness=run.faithfulness,
        answer_relevancy=run.answer_relevancy,
        context_recall=run.context_recall,
        context_precision=run.context_precision,
        error_message=run.error_message,
        created_at=run.created_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
    )


@router.get("/runs", response_model=list[EvalRunResponse])
def list_eval_runs(
    db: Session = Depends(get_db),
    user: User = Depends(require_tenant_admin()),
) -> list[EvalRunResponse]:
    runs = (
        db.query(EvaluationRun)
        .filter(EvaluationRun.tenant_id == user.tenant_id)
        .order_by(EvaluationRun.created_at.desc())
        .limit(50)
        .all()
    )
    return [_run_to_response(r) for r in runs]


@router.get("/runs/{run_id}", response_model=EvalRunResponse)
def get_eval_run(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_tenant_admin()),
) -> EvalRunResponse:
    run = (
        db.query(EvaluationRun)
        .filter(
            EvaluationRun.id == run_id,
            EvaluationRun.tenant_id == user.tenant_id,
        )
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Eval run not found")
    return _run_to_response(run)
