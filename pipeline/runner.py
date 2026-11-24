"""End-to-end Pipeline Orchestrator (Step 8).

Executes the complete document analysis pipeline in strict sequential order:
  1. Raw File Inspection (ingest.flags): Scan raw bytes/DOCX/PDF for manipulation.
  2. Text Sanitization (ingest.sanitizer): Strip invisible chars & normalize homoglyphs.
  3. Parsing & Windowing (ingest.parser, ingest.chunker): Clean headers/footers/refs.
  4. AI Detection + Similarity Suite:
     - AI: 2-signal calibrated ensemble + GLTR token forensics.
     - Similarity: LSH candidate filtering -> Winnowing exact slices + FAISS paraphrase search -> Aggregator.
  5. Unified Output: Assemble validated UnifiedOriginalityReport.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Any

from detectors.ensemble import AIEnsembleDetector
from ingest import flags, parser, sanitizer
from pipeline.schemas import (
    AIDetectionReport,
    DocumentMetadata,
    IntegrityFlagItem,
    IntegrityReport,
    SimilarityReport,
    SummaryCard,
    UnifiedOriginalityReport,
)
from similarity.aggregator import aggregate_similarity
from similarity.lsh import MinHashIndex
from similarity.semantic import SemanticIndex
from similarity.winnow import find_exact_matches


class PipelineRunner:
    def __init__(
        self,
        ensemble: AIEnsembleDetector | None = None,
        lsh_index: MinHashIndex | None = None,
        semantic_index: SemanticIndex | None = None,
        document_archive: dict[str, str] | None = None,
    ) -> None:
        self.ensemble = ensemble or AIEnsembleDetector()
        self.lsh_index = lsh_index or MinHashIndex()
        self.semantic_index = semantic_index or SemanticIndex()
        # In-memory document archive {doc_id: raw_text} for similarity comparisons
        self.document_archive = document_archive or {}

    def add_archive_document(self, doc_id: str, text: str) -> None:
        """Add a reference document to the similarity comparison archive."""
        self.document_archive[doc_id] = text
        self.lsh_index.index_document(doc_id, text)
        self.semantic_index.index_document(doc_id, text)

    def analyze_file(
        self,
        file_path: str | Path,
        report_id: str | None = None,
    ) -> UnifiedOriginalityReport:
        """Execute the full 5-stage analysis pipeline on an uploaded file."""
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        t0 = time.time()
        file_size = path.stat().st_size
        suffix = path.suffix.lower()
        file_type = suffix.lstrip(".") if suffix else "txt"

        # ------------------------------------------------------------------
        # Stage 1: Raw File Inspection (Red Flag detector)
        # ------------------------------------------------------------------
        raw_flags = flags.inspect_file(path)

        flag_items: list[IntegrityFlagItem] = []
        categories_found: set[str] = set()
        for fl in raw_flags:
            categories_found.add(fl.category)
            flag_items.append(
                IntegrityFlagItem(
                    category=fl.category,
                    kind=fl.kind,
                    severity="high" if fl.category == "hidden_text" else "medium",
                    location=fl.location,
                    instances=fl.instances,
                    summary=fl.summary() if callable(getattr(fl, "summary", None)) else str(getattr(fl, "summary", "")),
                )
            )

        # ------------------------------------------------------------------
        # Stage 2: Document Parsing (Headers/Footers & References stripped)
        # ------------------------------------------------------------------
        parsed_doc = parser.parse(path)
        raw_extracted_text = parsed_doc.text
        raw_words = len(raw_extracted_text.split())

        # ------------------------------------------------------------------
        # Stage 3: Sanitization (Pre-scoring normalization)
        # ------------------------------------------------------------------
        # Strip hidden/invisible codepoints and normalize homoglyphs to Latin
        sanitize_result = sanitizer.sanitize(raw_extracted_text)
        sanitized_text = sanitize_result.text
        sanitized_words = len(sanitized_text.split())

        # ------------------------------------------------------------------
        # Stage 4A: AI Detection (Ensemble + Guardrails + GLTR ranks)
        # ------------------------------------------------------------------
        ai_pred = self.ensemble.predict_document(sanitized_text)

        ai_report = AIDetectionReport(
            status=ai_pred.status,
            message=ai_pred.message,
            document_ai_pct=ai_pred.document_ai_pct,
            qualitative_label=ai_pred.qualitative_label,
            disclaimer=ai_pred.disclaimer,
            is_english=ai_pred.is_english,
            confidence_warning=ai_pred.confidence_warning,
            flagged_windows_count=sum(1 for w in ai_pred.windows if w.is_ai),
            total_windows_count=len(ai_pred.windows),
            windows=[w.to_dict() for w in ai_pred.windows],
        )

        # ------------------------------------------------------------------
        # Stage 4B: Similarity Detection (LSH -> Winnowing + FAISS -> Aggregator)
        # ------------------------------------------------------------------
        # Candidate search via MinHash LSH
        candidate_ids = self.lsh_index.query_candidates(sanitized_text)

        # Winnowing exact matches against candidate documents
        exact_matches_by_source = {}
        for cand_id in candidate_ids:
            if cand_id in self.document_archive:
                source_text = self.document_archive[cand_id]
                spans = find_exact_matches(sanitized_text, source_text, k=5, window_size=4)
                if spans:
                    exact_matches_by_source[cand_id] = spans

        # Semantic paraphrase vector search via FAISS
        semantic_matches = self.semantic_index.search_text(
            sanitized_text,
            min_similarity=0.59,
        )

        # Deduplicated aggregation matching Dolos fragment spec
        agg_report = aggregate_similarity(
            query_text=sanitized_text,
            exact_matches_by_source=exact_matches_by_source,
            semantic_matches=semantic_matches,
            min_paraphrase_similarity=0.59,
        )

        sim_report = SimilarityReport(
            total_similarity_pct=agg_report.total_similarity_pct,
            exact_similarity_pct=agg_report.exact_similarity_pct,
            paraphrase_similarity_pct=agg_report.paraphrase_similarity_pct,
            matched_words=agg_report.matched_words,
            total_words=agg_report.total_words,
            sources_count=len(agg_report.sources_breakdown),
            sources_breakdown=[s.to_dict() for s in agg_report.sources_breakdown],
            fragments=[f.to_dict() for f in agg_report.merged_fragments],
        )

        # ------------------------------------------------------------------
        # Stage 5: Unified Output Assembly
        # ------------------------------------------------------------------
        proc_time = round(time.time() - t0, 3)
        metadata = DocumentMetadata(
            filename=path.name,
            file_type=file_type,
            file_size_bytes=file_size,
            raw_word_count=raw_words,
            sanitized_word_count=sanitized_words,
            processing_time_seconds=proc_time,
        )

        integrity_report = IntegrityReport(
            total_flags=len(flag_items),
            has_tampering=len(flag_items) > 0,
            categories_found=sorted(categories_found),
            flags=flag_items,
        )

        # UI Summary card
        summary_card = SummaryCard(
            ai_pct=ai_report.document_ai_pct,
            similarity_pct=sim_report.total_similarity_pct,
            red_flags_count=integrity_report.total_flags,
            qualitative_label=ai_report.qualitative_label,
            disclaimer=ai_report.disclaimer,
        )

        return UnifiedOriginalityReport(
            report_id=report_id or str(uuid.uuid4()),
            metadata=metadata,
            integrity=integrity_report,
            ai_detection=ai_report,
            similarity=sim_report,
            summary_card=summary_card,
        )
