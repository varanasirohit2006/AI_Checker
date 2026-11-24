"""Assignment Endpoints (Step 9).

Allows teachers to create, list, and manage assignments and classes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.models import Assignment, Submission, User

router = APIRouter(prefix="/assignments", tags=["assignments"])


class AssignmentCreate(BaseModel):
    title: str
    description: str | None = None
    class_name: str = "Default Class"


class AssignmentResponse(BaseModel):
    id: str
    teacher_id: str
    title: str
    description: str | None
    class_name: str
    created_at: datetime
    submissions_count: int = 0

    class Config:
        from_attributes = True


@router.post("", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
def create_assignment(
    req: AssignmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assignment = Assignment(
        teacher_id=current_user.id,
        title=req.title,
        description=req.description,
        class_name=req.class_name,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    res = AssignmentResponse.from_orm(assignment)
    res.submissions_count = 0
    return res


@router.get("", response_model=list[AssignmentResponse])
def list_assignments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assignments = db.query(Assignment).filter(Assignment.teacher_id == current_user.id).all()
    results = []
    for a in assignments:
        count = db.query(Submission).filter(Submission.assignment_id == a.id).count()
        resp = AssignmentResponse.from_orm(a)
        resp.submissions_count = count
        results.append(resp)
    return results


@router.get("/{assignment_id}", response_model=AssignmentResponse)
def get_assignment(
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

    count = db.query(Submission).filter(Submission.assignment_id == assignment.id).count()
    resp = AssignmentResponse.from_orm(assignment)
    resp.submissions_count = count
    return resp
