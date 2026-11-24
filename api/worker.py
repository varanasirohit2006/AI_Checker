"""Async Worker & Pipeline Execution Queue (Step 9).

Separates CPU tasks (parsing, Integrity Flags, Winnowing, LSH) from GPU tasks
(AI detection, GLTR token ranks). Supports:
  1. In-process async background tasks (fast execution / testing)
  2. Celery / RQ queue task definition when Redis is present.
"""

from __future__ import annotations

import json
import logging
import os
import traceback
from pathlib import Path

from sqlalchemy.orm import Session

from api.database import SessionLocal
from api.models import Fingerprint, IntegrityFlag, Report, Submission
from pipeline.runner import PipelineRunner
from similarity.winnow import get_fingerprints

logger = logging.getLogger("api.worker")

# Shared pipeline runner instance
_runner: PipelineRunner | None = None


def get_pipeline_runner() -> PipelineRunner:
    global _runner
    if _runner is None:
        _runner = PipelineRunner()
    return _runner


def process_submission_task(submission_id: str) -> None:
    """Entry point for async background worker task."""
    db: Session = SessionLocal()
    try:
        sub = db.query(Submission).filter(Submission.id == submission_id).first()
        if not sub:
            logger.error(f"Submission {submission_id} not found")
            return

        # 1. Update status to processing
        sub.status = "processing"
        # Idempotency: clean up any existing records if reprocessing
        db.query(Report).filter(Report.submission_id == submission_id).delete()
        db.query(IntegrityFlag).filter(IntegrityFlag.submission_id == submission_id).delete()
        db.query(Fingerprint).filter(Fingerprint.submission_id == submission_id).delete()
        db.commit()

        # 2. Run the 5-stage pipeline orchestrator
        runner = get_pipeline_runner()
        report_data = runner.analyze_file(sub.file_path, report_id=submission_id)

        # 3. Persist Integrity Flags
        for fl in report_data.integrity.flags:
            db_flag = IntegrityFlag(
                submission_id=submission_id,
                category=fl.category,
                kind=fl.kind,
                severity=fl.severity,
                location_json=json.dumps(fl.location),
                instances_json=json.dumps(fl.instances),
                summary=fl.summary,
            )
            db.add(db_flag)

        # 4. Extract and persist Winnowing Fingerprints for future archive comparisons
        from ingest import parser

        parsed = parser.parse(sub.file_path)
        fps = get_fingerprints(parsed.text, k=5, window_size=4)
        for fp in fps:
            db_fp = Fingerprint(
                submission_id=submission_id,
                hash_val=str(fp.hash_val),
                start_char=fp.start_char,
                end_char=fp.end_char,
                token_idx=fp.token_idx,
            )
            db.add(db_fp)

        # Also add this document to the runner's in-memory archive
        runner.add_archive_document(submission_id, parsed.text)

        # 5. Persist Unified Report
        db_report = Report(
            submission_id=submission_id,
            report_json=report_data.to_json(),
            document_ai_pct=report_data.ai_detection.document_ai_pct,
            total_similarity_pct=report_data.similarity.total_similarity_pct,
            red_flags_count=report_data.integrity.total_flags,
            qualitative_label=report_data.summary_card.qualitative_label,
        )
        db.add(db_report)

        # 6. Mark submission as done
        sub.status = "done"
        db.commit()
        logger.info(f"Submission {submission_id} successfully processed")

    except Exception as exc:
        db.rollback()
        err_msg = f"{type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}"
        logger.error(f"Failed processing submission {submission_id}: {err_msg}")
        sub = db.query(Submission).filter(Submission.id == submission_id).first()
        if sub:
            sub.status = "failed"
            sub.error_message = err_msg[:1000]
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        sub_id = sys.argv[1]
        print(f"Running worker task for submission: {sub_id}")
        process_submission_task(sub_id)
    else:
        print("Originality Worker listening (standalone mode)...")
