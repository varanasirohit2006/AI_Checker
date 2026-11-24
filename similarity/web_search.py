"""Web Search Similarity Module (Step 12, Iteration 2).

Extracts 10–20 distinctive, high-information sentences from a sanitized document,
enforces a strict per-document query budget cap (10–20 queries max), fetches
candidate web pages, and runs Winnowing exact-match comparison to detect web plagiarism
(e.g., copied Wikipedia paragraphs).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from similarity.winnow import find_exact_matches, get_fingerprints

logger = logging.getLogger(__name__)

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
WORD_RE = re.compile(r"\b\w+\b")

DEFAULT_MAX_QUERIES_CAP = 15
MIN_SENTENCE_WORDS = 8
MAX_SENTENCE_WORDS = 40


@dataclass
class WebMatch:
    url: str
    title: str
    similarity_pct: float
    matched_text: str
    source_snippet: str
    match_type: str = "exact"  # "exact" | "paraphrase"

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "similarity_pct": round(self.similarity_pct, 2),
            "matched_text": self.matched_text,
            "source_snippet": self.source_snippet,
            "match_type": self.match_type,
        }


@dataclass
class WebSimilarityReport:
    enabled: bool
    queries_used: int
    query_cap: int
    matches_found_count: int
    overall_web_overlap_pct: float
    matches: list[WebMatch] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "queries_used": self.queries_used,
            "query_cap": self.query_cap,
            "matches_found_count": self.matches_found_count,
            "overall_web_overlap_pct": round(self.overall_web_overlap_pct, 2),
            "matches": [m.to_dict() for m in self.matches],
        }


def extract_distinctive_queries(
    text: str,
    max_queries: int = DEFAULT_MAX_QUERIES_CAP,
) -> list[str]:
    """Select the most distinctive, high-information sentences for search."""
    raw_sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
    candidates = []

    for s in raw_sentences:
        words = WORD_RE.findall(s)
        n_w = len(words)
        if MIN_SENTENCE_WORDS <= n_w <= MAX_SENTENCE_WORDS:
            # Score distinctiveness: length + presence of specialized capitalized nouns
            caps = sum(1 for w in words[1:] if w[0].isupper())
            distinctiveness = n_w + (caps * 3)
            candidates.append((distinctiveness, s))

    # Sort descending by distinctiveness
    candidates.sort(key=lambda x: x[0], reverse=True)
    selected = [c[1] for c in candidates[:max_queries]]
    return selected


class WebSearchSimilarityChecker:
    def __init__(
        self,
        max_queries_cap: int = DEFAULT_MAX_QUERIES_CAP,
        search_engine_fn: Callable[[str], list[dict[str, str]]] | None = None,
    ) -> None:
        self.max_queries_cap = min(20, max(5, max_queries_cap))
        self.search_engine_fn = search_engine_fn

    def check_web_similarity(
        self,
        document_text: str,
        mock_web_index: dict[str, str] | None = None,
    ) -> WebSimilarityReport:
        """Run bounded web search similarity check against document text."""
        queries = extract_distinctive_queries(document_text, max_queries=self.max_queries_cap)
        queries_used = len(queries)

        matches: list[WebMatch] = []
        target_web_pages: dict[str, dict[str, str]] = {}

        if mock_web_index:
            # Testing mode with local web index (e.g. Wikipedia articles)
            for url, page_text in mock_web_index.items():
                target_web_pages[url] = {
                    "url": url,
                    "title": url.split("/")[-1].replace("_", " ").title(),
                    "content": page_text,
                }
        elif self.search_engine_fn:
            for q in queries:
                results = self.search_engine_fn(q)
                for res in results:
                    url = res.get("url", "")
                    if url and url not in target_web_pages:
                        target_web_pages[url] = res

        # Run Winnowing comparison against retrieved candidate pages
        matched_sentences_count = 0
        total_queries = max(len(queries), 1)

        for q in queries:
            matched_for_q = False
            for url, page_info in target_web_pages.items():
                content = page_info.get("content", "")
                exact_spans = find_exact_matches(q, content, k=4, window_size=4)
                if exact_spans:
                    matched_for_q = True
                    match_snippet = exact_spans[0].text if hasattr(exact_spans[0], "text") else q[:60]
                    matches.append(
                        WebMatch(
                            url=url,
                            title=page_info.get("title", url),
                            similarity_pct=100.0,
                            matched_text=q,
                            source_snippet=match_snippet,
                            match_type="exact",
                        )
                    )
                    break
            if matched_for_q:
                matched_sentences_count += 1

        overall_pct = (matched_sentences_count / total_queries) * 100.0

        return WebSimilarityReport(
            enabled=True,
            queries_used=queries_used,
            query_cap=self.max_queries_cap,
            matches_found_count=len(matches),
            overall_web_overlap_pct=overall_pct,
            matches=matches,
        )
