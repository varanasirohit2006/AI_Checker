"""Similarity Score Aggregator & Dolos Fragment Exporter (Step 6).

Merges overlapping exact-copy spans (from similarity.winnow) and paraphrase
spans (from similarity.semantic) without double-counting words. Computes:
  * Total Similarity %
  * Exact Match %
  * Paraphrase %
  * Per-source breakdown matching the Dolos fragment schema.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from similarity.semantic import SemanticMatch
from similarity.winnow import ExactMatchSpan

WORD_RE = re.compile(r"\b\S+\b")


@dataclass
class Fragment:
    fragment_type: str  # "exact" | "paraphrase"
    query_start_char: int
    query_end_char: int
    query_text: str
    source_id: str
    source_start_char: int
    source_end_char: int
    similarity_score: float
    severity: str  # "exact" | "high" | "medium" | "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.fragment_type,
            "query_start_char": self.query_start_char,
            "query_end_char": self.query_end_char,
            "query_text": self.query_text,
            "source_id": self.source_id,
            "source_start_char": self.source_start_char,
            "source_end_char": self.source_end_char,
            "similarity_score": round(self.similarity_score, 4),
            "severity": self.severity,
        }


@dataclass
class SourceBreakdown:
    source_id: str
    matched_words: int
    similarity_pct: float
    fragments: list[Fragment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "matched_words": self.matched_words,
            "similarity_pct": round(self.similarity_pct, 2),
            "fragments": [f.to_dict() for f in self.fragments],
        }


@dataclass
class AggregatedSimilarityReport:
    total_words: int
    matched_words: int
    total_similarity_pct: float
    exact_similarity_pct: float
    paraphrase_similarity_pct: float
    merged_fragments: list[Fragment] = field(default_factory=list)
    sources_breakdown: list[SourceBreakdown] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_words": self.total_words,
            "matched_words": self.matched_words,
            "total_similarity_pct": round(self.total_similarity_pct, 2),
            "exact_similarity_pct": round(self.exact_similarity_pct, 2),
            "paraphrase_similarity_pct": round(self.paraphrase_similarity_pct, 2),
            "merged_fragments": [f.to_dict() for f in self.merged_fragments],
            "sources_breakdown": [s.to_dict() for s in self.sources_breakdown],
        }


def aggregate_similarity(
    query_text: str,
    exact_matches_by_source: dict[str, list[ExactMatchSpan]],
    semantic_matches: list[SemanticMatch],
    min_paraphrase_similarity: float = 0.59,
) -> AggregatedSimilarityReport:
    """Merge exact and paraphrase spans without double-counting words.

    Exact matches take precedence over paraphrase matches for overlapping words.
    Only paraphrase matches with similarity >= min_paraphrase_similarity (default 0.75)
    are included in the official similarity percentage (lower matches remain accessible
    for auxiliary inspection if desired).
    """
    word_matches = list(WORD_RE.finditer(query_text))
    total_words = len(word_matches)
    if total_words == 0:
        return AggregatedSimilarityReport(
            total_words=0,
            matched_words=0,
            total_similarity_pct=0.0,
            exact_similarity_pct=0.0,
            paraphrase_similarity_pct=0.0,
        )

    # Word-level coverage tracking:
    # 0 = clean, 1 = exact match, 2 = paraphrase match
    word_status = [0] * total_words
    word_sources: list[set[str]] = [set() for _ in range(total_words)]

    # Collect all fragments for reporting
    all_fragments: list[Fragment] = []

    # 1. Process Exact Matches
    for source_id, spans in exact_matches_by_source.items():
        for span in spans:
            fragment = Fragment(
                fragment_type="exact",
                query_start_char=span.doc_a_start,
                query_end_char=span.doc_a_end,
                query_text=span.text_a,
                source_id=source_id,
                source_start_char=span.doc_b_start,
                source_end_char=span.doc_b_end,
                similarity_score=1.0,
                severity="exact",
            )
            all_fragments.append(fragment)

            # Mark matching words
            for w_idx, w in enumerate(word_matches):
                if w.start() >= span.doc_a_start and w.end() <= span.doc_a_end:
                    word_status[w_idx] = 1
                    word_sources[w_idx].add(source_id)

    # 2. Process Semantic Paraphrase Matches (>= min_paraphrase_similarity)
    filtered_semantic = [m for m in semantic_matches if m.similarity >= min_paraphrase_similarity]
    for sm in filtered_semantic:
        fragment = Fragment(
            fragment_type="paraphrase",
            query_start_char=sm.query_start_char,
            query_end_char=sm.query_end_char,
            query_text=sm.query_text,
            source_id=sm.matched_doc_id,
            source_start_char=sm.matched_start_char,
            source_end_char=sm.matched_end_char,
            similarity_score=sm.similarity,
            severity=sm.severity,
        )
        all_fragments.append(fragment)

        # Mark matching words (only if not already marked as exact)
        for w_idx, w in enumerate(word_matches):
            if w.start() >= sm.query_start_char and w.end() <= sm.query_end_char:
                if word_status[w_idx] == 0:
                    word_status[w_idx] = 2
                word_sources[w_idx].add(sm.matched_doc_id)

    # Sort fragments by query_start_char
    all_fragments.sort(key=lambda f: f.query_start_char)

    # Calculate overall metrics
    exact_words = sum(1 for s in word_status if s == 1)
    paraphrase_words = sum(1 for s in word_status if s == 2)
    matched_words = exact_words + paraphrase_words

    total_pct = (matched_words / total_words) * 100.0
    exact_pct = (exact_words / total_words) * 100.0
    paraphrase_pct = (paraphrase_words / total_words) * 100.0

    # Per-source breakdown
    all_source_ids = set()
    for s_set in word_sources:
        all_source_ids.update(s_set)

    sources_breakdown: list[SourceBreakdown] = []
    for s_id in sorted(all_source_ids):
        s_words = sum(1 for s_set in word_sources if s_id in s_set)
        s_pct = (s_words / total_words) * 100.0
        s_frags = [f for f in all_fragments if f.source_id == s_id]
        sources_breakdown.append(
            SourceBreakdown(
                source_id=s_id,
                matched_words=s_words,
                similarity_pct=s_pct,
                fragments=s_frags,
            )
        )

    # Sort sources breakdown by matched_words descending
    sources_breakdown.sort(key=lambda s: s.matched_words, reverse=True)

    return AggregatedSimilarityReport(
        total_words=total_words,
        matched_words=matched_words,
        total_similarity_pct=total_pct,
        exact_similarity_pct=exact_pct,
        paraphrase_similarity_pct=paraphrase_pct,
        merged_fragments=all_fragments,
        sources_breakdown=sources_breakdown,
    )
