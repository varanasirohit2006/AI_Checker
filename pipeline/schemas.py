"""Data schemas for the unified Originality Report (Step 8).

Defines the structure for the complete document analysis payload:
  * Document metadata
  * Integrity Flags (Red Flags) with exact coordinates
  * AI Detection scores (Window-to-document rollup + GLTR ranks)
  * Similarity scores (Exact + Paraphrase breakdown matching Dolos spec)
  * Summary card for teacher dashboard UI
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DocumentMetadata:
    filename: str
    file_type: str  # "docx" | "pdf" | "txt"
    file_size_bytes: int
    raw_word_count: int
    sanitized_word_count: int
    analyzed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    processing_time_seconds: float = 0.0


@dataclass
class IntegrityFlagItem:
    category: str  # "replaced_character" | "hidden_unicode" | "hidden_text"
    kind: str
    severity: str  # "high" | "medium" | "low"
    location: dict[str, Any]
    instances: list[dict[str, Any]]
    summary: str


@dataclass
class IntegrityReport:
    total_flags: int
    has_tampering: bool
    categories_found: list[str]
    flags: list[IntegrityFlagItem] = field(default_factory=list)


@dataclass
class AIDetectionReport:
    status: str  # "DONE" | "TOO_SHORT"
    message: str
    document_ai_pct: float | None
    qualitative_label: str
    disclaimer: str
    is_english: bool
    confidence_warning: str | None
    flagged_windows_count: int
    total_windows_count: int
    windows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SimilarityReport:
    total_similarity_pct: float
    exact_similarity_pct: float
    paraphrase_similarity_pct: float
    matched_words: int
    total_words: int
    sources_count: int
    sources_breakdown: list[dict[str, Any]] = field(default_factory=list)
    fragments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SummaryCard:
    ai_pct: float | None
    similarity_pct: float
    red_flags_count: int
    qualitative_label: str
    disclaimer: str


@dataclass
class UnifiedOriginalityReport:
    report_id: str
    metadata: DocumentMetadata
    integrity: IntegrityReport
    ai_detection: AIDetectionReport
    similarity: SimilarityReport
    summary_card: SummaryCard

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        def _default(o):
            return o() if callable(o) else str(o)

        return json.dumps(self.to_dict(), indent=indent, default=_default)
