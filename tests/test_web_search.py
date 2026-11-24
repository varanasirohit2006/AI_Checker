"""Tests for Web Search Similarity Module (Step 12, Sub-task 2).

Verifies:
  1. Strict 10-20 query cap per document.
  2. Distinctive sentence query extraction logic.
  3. Accurate detection of copied Wikipedia text against web candidates.

Run: .venv/Scripts/python.exe tests/test_web_search.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from similarity.web_search import (
    WebSearchSimilarityChecker,
    extract_distinctive_queries,
)

WIKIPEDIA_PHOTOSYNTHESIS = (
    "Photosynthesis is a biological process used by many cellular organisms to convert light energy into chemical energy. "
    "This chemical energy is stored in carbohydrate molecules, such as sugars, which are synthesized from carbon dioxide and water. "
    "The process of photosynthesis is largely responsible for producing and maintaining the oxygen content of the Earth's atmosphere."
)

STUDENT_ESSAY_WITH_WIKI_COPY = (
    "In this high school biology paper, we explore the origins of biochemical energy in ecosystems. "
    "Photosynthesis is a biological process used by many cellular organisms to convert light energy into chemical energy. "
    "This chemical energy is stored in carbohydrate molecules, such as sugars, which are synthesized from carbon dioxide and water. "
    "Our field observations at the botanical garden confirmed plant respiration rates in high sunlight environments."
)

ORIGINAL_STUDENT_ESSAY = (
    "During my summer volunteer work at the community conservatory, I observed several species of ferns and mosses. "
    "We documented the soil moisture levels and monitored ambient temperature fluctuations throughout the greenhouse daily. "
    "The data collected indicated that humidity retention plays a significant role in seedling survival rates."
)


class TestWebSearchSimilarity(unittest.TestCase):
    def test_01_query_cap_enforcement(self):
        checker = WebSearchSimilarityChecker(max_queries_cap=15)
        # Long text with 30 sentences
        long_text = ("This is a distinctive sentence exploring academic principles in university courses. " * 30)
        queries = extract_distinctive_queries(long_text, max_queries=checker.max_queries_cap)
        self.assertLessEqual(len(queries), 15)
        self.assertGreaterEqual(len(queries), 1)

    def test_02_detect_copied_wikipedia_paragraph(self):
        checker = WebSearchSimilarityChecker(max_queries_cap=10)
        mock_web_index = {
            "https://en.wikipedia.org/wiki/Photosynthesis": WIKIPEDIA_PHOTOSYNTHESIS,
            "https://en.wikipedia.org/wiki/Cellular_respiration": "Cellular respiration is a set of metabolic reactions.",
        }

        report = checker.check_web_similarity(
            document_text=STUDENT_ESSAY_WITH_WIKI_COPY,
            mock_web_index=mock_web_index,
        )

        self.assertTrue(report.enabled)
        self.assertGreater(report.matches_found_count, 0)
        self.assertGreater(report.overall_web_overlap_pct, 0.0)

        # Check matched source details
        matched_urls = [m.url for m in report.matches]
        self.assertIn("https://en.wikipedia.org/wiki/Photosynthesis", matched_urls)
        self.assertEqual(report.matches[0].match_type, "exact")

    def test_03_original_essay_zero_web_overlap(self):
        checker = WebSearchSimilarityChecker(max_queries_cap=10)
        mock_web_index = {
            "https://en.wikipedia.org/wiki/Photosynthesis": WIKIPEDIA_PHOTOSYNTHESIS,
        }

        report = checker.check_web_similarity(
            document_text=ORIGINAL_STUDENT_ESSAY,
            mock_web_index=mock_web_index,
        )

        self.assertEqual(report.matches_found_count, 0)
        self.assertEqual(report.overall_web_overlap_pct, 0.0)


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
