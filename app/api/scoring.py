from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import ScoringJobResponse
from app.services.scoring import enqueue_scoring_job
from app.services.scoring import retry_scoring_job
from app.services.authorization import require_hr_mock_token

router = APIRouter(prefix="/scoring", tags=["scoring"])


@router.post("/answers/{answer_id}", response_model=ScoringJobResponse, status_code=202)
def queue_answer_for_scoring(answer_id: str, db: Session = Depends(get_db)) -> ScoringJobResponse:
    try:
        return enqueue_scoring_job(db, answer_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/answers/{answer_id}/retry", response_model=ScoringJobResponse)
def retry_answer_scoring(
    answer_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_hr_mock_token),
) -> ScoringJobResponse:
    try:
        return retry_scoring_job(db, answer_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
