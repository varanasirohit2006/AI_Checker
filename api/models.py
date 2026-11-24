"""Database Models (Step 9).

PostgreSQL / SQLAlchemy models for:
  * Users (teacher isolation)
  * Assignments
  * Submissions (queued / processing / done / failed)
  * IntegrityFlags (structured JSON coordinates)
  * Fingerprints (Winnowing hashes for archive matching)
  * Reports (Unified analysis JSON payload)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from api.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), default="teacher", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    assignments = relationship("Assignment", back_populates="teacher", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="teacher", cascade="all, delete-orphan")


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    teacher_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    class_name = Column(String(100), nullable=False, default="Default Class")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    teacher = relationship("User", back_populates="assignments")
    submissions = relationship("Submission", back_populates="assignment", cascade="all, delete-orphan")


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    assignment_id = Column(String(36), ForeignKey("assignments.id"), nullable=False, index=True)
    teacher_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(1024), nullable=False)
    file_size_bytes = Column(Integer, default=0)
    status = Column(String(50), default="queued", nullable=False, index=True)  # queued, processing, done, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    teacher = relationship("User", back_populates="submissions")
    assignment = relationship("Assignment", back_populates="submissions")
    report = relationship("Report", back_populates="submission", uselist=False, cascade="all, delete-orphan")
    integrity_flags = relationship("IntegrityFlag", back_populates="submission", cascade="all, delete-orphan")
    fingerprints = relationship("Fingerprint", back_populates="submission", cascade="all, delete-orphan")


class IntegrityFlag(Base):
    __tablename__ = "integrity_flags"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    submission_id = Column(String(36), ForeignKey("submissions.id"), nullable=False, index=True)
    category = Column(String(100), nullable=False)  # replaced_character, hidden_unicode, hidden_text
    kind = Column(String(100), nullable=False)
    severity = Column(String(50), default="medium", nullable=False)
    location_json = Column(Text, nullable=False)  # JSON-encoded coordinates
    instances_json = Column(Text, nullable=False)  # JSON-encoded instances
    summary = Column(Text, nullable=False)

    submission = relationship("Submission", back_populates="integrity_flags")


class Fingerprint(Base):
    __tablename__ = "fingerprints"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    submission_id = Column(String(36), ForeignKey("submissions.id"), nullable=False, index=True)
    hash_val = Column(String(64), nullable=False, index=True)
    start_char = Column(Integer, nullable=False)
    end_char = Column(Integer, nullable=False)
    token_idx = Column(Integer, nullable=False)

    submission = relationship("Submission", back_populates="fingerprints")


class Report(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    submission_id = Column(String(36), ForeignKey("submissions.id"), unique=True, nullable=False, index=True)
    report_json = Column(Text, nullable=False)  # Full UnifiedOriginalityReport JSON
    document_ai_pct = Column(Float, nullable=True)
    total_similarity_pct = Column(Float, default=0.0, nullable=False)
    red_flags_count = Column(Integer, default=0, nullable=False)
    qualitative_label = Column(String(100), default="Analysis complete", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    submission = relationship("Submission", back_populates="report")
