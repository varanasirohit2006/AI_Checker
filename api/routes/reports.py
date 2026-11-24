"""Report Endpoints (Step 9).

Retrieves the full unified originality report payload (Dolos fragments,
GLTR token ranks, Integrity Flags, and AI/Similarity scores).
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.export import generate_pdf_report
from api.models import Report, Submission, User

router = APIRouter(tags=["reports"])


@router.get("/submissions/{submission_id}/report")
def get_submission_report(
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

    if sub.status == "queued" or sub.status == "processing":
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail=f"Report is still {sub.status}. Please poll again shortly.",
        )
    if sub.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {sub.error_message}",
        )

    if not sub.report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report record not found")

    try:
        report_dict = json.loads(sub.report.report_json)
        return report_dict
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Corrupted report data: {str(exc)}",
        )


@router.get("/submissions/{submission_id}/export")
def export_submission_pdf(
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

    if not sub.report:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Report not ready (status: {sub.status})",
        )

    try:
        report_dict = json.loads(sub.report.report_json)
        pdf_stream = generate_pdf_report(report_dict)
        pdf_bytes = pdf_stream.getvalue()

        clean_filename = sub.filename.rsplit(".", 1)[0]
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="originality_report_{clean_filename}.pdf"'
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF: {str(exc)}",
        )


@router.get("/reports/{report_id}")
def get_report_by_id(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    sub = db.query(Submission).filter(Submission.id == report.submission_id).first()
    if not sub or sub.teacher_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return json.loads(report.report_json)
