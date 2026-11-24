"""Submission Endpoints (Step 9).

Handles document uploads, streaming to storage, asynchronous background queuing,
and live status polling.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.models import Assignment, Report, Submission, User
from api.storage import StorageClient
from api.worker import process_submission_task

router = APIRouter(tags=["submissions"])
storage_client = StorageClient()


class SubmissionResponse(BaseModel):
    id: str
    assignment_id: str
    teacher_id: str
    filename: str
    file_size_bytes: int
    status: str
    error_message: str | None = None
    created_at: datetime
    document_ai_pct: float | None = None
    total_similarity_pct: float | None = None
    red_flags_count: int | None = None

    class Config:
        from_attributes = True


@router.post(
    "/assignments/{assignment_id}/upload",
    response_model=SubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_submission(
    assignment_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assignment = (
        db.query(Assignment)
        .filter(Assignment.id == assignment_id, Assignment.teacher_id == current_user.id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    # Read uploaded bytes
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
    MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB limit
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of 25MB ({len(content)} bytes uploaded)",
        )

    submission = Submission(
        assignment_id=assignment.id,
        teacher_id=current_user.id,
        filename=file.filename or "uploaded_file",
        file_path="",
        file_size_bytes=len(content),
        status="queued",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    # Save to storage
    file_path = storage_client.save_file(submission.id, submission.filename, content)
    submission.file_path = file_path
    db.commit()

    # Enqueue async background task
    background_tasks.add_task(process_submission_task, submission.id)

    return SubmissionResponse.from_orm(submission)


@router.get("/submissions/{submission_id}/status", response_model=SubmissionResponse)
def get_submission_status(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = (
        db.query(Submission)
        .filter(Submission.id == submission_id, Submission.teacher_id == current_user.id)
        .first()
    )
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    resp = SubmissionResponse.from_orm(sub)
    if sub.report:
        resp.document_ai_pct = sub.report.document_ai_pct
        resp.total_similarity_pct = sub.report.total_similarity_pct
        resp.red_flags_count = sub.report.red_flags_count

    return resp


@router.get("/assignments/{assignment_id}/submissions", response_model=list[SubmissionResponse])
def list_assignment_submissions(
    assignment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assignment = (
        db.query(Assignment)
        .filter(Assignment.id == assignment_id, Assignment.teacher_id == current_user.id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    submissions = (
        db.query(Submission)
        .filter(Submission.assignment_id == assignment.id)
        .order_by(Submission.created_at.desc())
        .all()
    )

    results = []
    for s in submissions:
        resp = SubmissionResponse.from_orm(s)
        if s.report:
            resp.document_ai_pct = s.report.document_ai_pct
            resp.total_similarity_pct = s.report.total_similarity_pct
            resp.red_flags_count = s.report.red_flags_count
        results.append(resp)

    return results


@router.delete("/submissions/{submission_id}", status_code=status.HTTP_200_OK)
def delete_submission(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = (
        db.query(Submission)
        .filter(Submission.id == submission_id, Submission.teacher_id == current_user.id)
        .first()
    )
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    # Delete physical file from storage
    if sub.file_path:
        storage_client.delete_file(sub.file_path)

    # Delete cascade / related DB entities
    from api.models import Fingerprint, IntegrityFlag
    db.query(IntegrityFlag).filter(IntegrityFlag.submission_id == sub.id).delete()
    db.query(Fingerprint).filter(Fingerprint.submission_id == sub.id).delete()
    if sub.report:
        db.delete(sub.report)
    db.delete(sub)
    db.commit()

    return {"detail": "Submission, report, and associated student data deleted successfully"}
