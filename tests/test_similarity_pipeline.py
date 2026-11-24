"""Tests for Step 6 Similarity Pipeline (AGENTS.md & NEXT_STEPS_PLAYBOOK.md).

Covers:
  1. similarity.winnow: word tokenization, k-gram hashing, winnowing, exact match spans.
  2. similarity.lsh: MinHash LSH indexing, candidate retrieval, Jaccard estimation.
  3. similarity.semantic: sentence chunking, FAISS vector indexing, paraphrase retrieval (severity bands).
  4. similarity.aggregator: word-level deduplication, unified similarity %, per-source Dolos fragments.
  5. End-to-end integration: exact copies, paraphrased paragraphs, and unrelated essays.

Run:  .venv/Scripts/python.exe -m unittest tests.test_similarity_pipeline -v
  or: .venv/Scripts/python.exe tests/test_similarity_pipeline.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from similarity.aggregator import (
    AggregatedSimilarityReport,
    Fragment,
    SourceBreakdown,
    aggregate_similarity,
)
from similarity.lsh import MinHashIndex, compute_minhash, get_shingles
from similarity.semantic import (
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SemanticIndex,
    classify_severity,
    create_semantic_chunks,
)
from similarity.winnow import (
    ExactMatchSpan,
    extract_kgrams,
    find_exact_matches,
    get_fingerprints,
    tokenize_words,
)

# Benchmark test texts
SOURCE_ESSAY = (
    "Artificial intelligence is rapidly transforming higher education. Universities around "
    "the world are adopting automated grading systems, personalized tutoring agents, and "
    "adaptive learning environments to enhance student outcomes. However, the widespread "
    "availability of generative language models presents significant academic integrity "
    "challenges. Instructors must rethink traditional assessment strategies to ensure that "
    "students genuinely acquire critical thinking and synthesis skills."
)

EXACT_COPY_ESSAY = (
    "Here is an introduction to the topic. "
    + SOURCE_ESSAY
    + " In conclusion, educational institutions must balance technological adoption with academic rigor."
)

PARAPHRASED_ESSAY = (
    "Artificial intelligence is rapidly altering the environment of higher education. "
    "Colleges and universities worldwide are adopting automated grading tools, personalized virtual tutors, "
    "and responsive teaching platforms to improve educational achievement. Nonetheless, the widespread "
    "availability of generative language systems creates serious questions regarding scholastic honesty. "
    "Educators need to redesign traditional evaluation methods so students truly develop analytical reasoning "
    "and critical thinking skills."
)

UNRELATED_ESSAY = (
    "Photosynthesis is a biological process utilized by green plants, algae, and certain bacteria "
    "to convert solar radiant energy into chemical energy stored in glucose molecules. Chlorophyll "
    "pigments located inside chloroplast thylakoid membranes absorb light predominantly in the "
    "blue and red spectral wavelengths while reflecting green light. Carbon dioxide and water "
    "serve as reactants, releasing oxygen gas into the atmosphere as a byproduct."
)


class TestWinnowing(unittest.TestCase):
    def test_tokenize_words(self):
        tokens = tokenize_words("Hello, world! This is a test.")
        self.assertEqual(len(tokens), 6)
        self.assertEqual(tokens[0].norm, "hello")
        self.assertEqual(tokens[1].norm, "world")
        self.assertEqual(tokens[0].start, 0)
        self.assertEqual(tokens[0].end, 5)

    def test_kgrams_and_fingerprints(self):
        tokens = tokenize_words(SOURCE_ESSAY)
        kgrams = extract_kgrams(tokens, k=5)
        self.assertGreater(len(kgrams), 10)
        fps = get_fingerprints(SOURCE_ESSAY, k=5, window_size=4)
        self.assertGreater(len(fps), 0)
        self.assertLessEqual(len(fps), len(kgrams))

    def test_exact_matches_found(self):
        matches = find_exact_matches(EXACT_COPY_ESSAY, SOURCE_ESSAY, k=5, window_size=4)
        self.assertGreaterEqual(len(matches), 1)
        # Check that matched text matches the source
        first_match = matches[0]
        self.assertIn("Artificial intelligence is rapidly transforming", first_match.text_a)
        self.assertEqual(first_match.text_a, first_match.text_b)

    def test_unrelated_has_no_exact_matches(self):
        matches = find_exact_matches(UNRELATED_ESSAY, SOURCE_ESSAY, k=5, window_size=4)
        self.assertEqual(len(matches), 0)


class TestMinHashLSH(unittest.TestCase):
    def setUp(self):
        self.index = MinHashIndex(threshold=0.2, num_perm=128)
        self.index.index_document("source_1", SOURCE_ESSAY)
        self.index.index_document("unrelated_1", UNRELATED_ESSAY)

    def test_exact_copy_retrieved(self):
        candidates = self.index.query_candidates(EXACT_COPY_ESSAY)
        self.assertIn("source_1", candidates)

    def test_unrelated_not_retrieved_for_query(self):
        candidates = self.index.query_candidates(UNRELATED_ESSAY)
        self.assertIn("unrelated_1", candidates)
        self.assertNotIn("source_1", candidates)

    def test_jaccard_estimation(self):
        sim_high = self.index.estimate_jaccard(SOURCE_ESSAY, EXACT_COPY_ESSAY)
        sim_low = self.index.estimate_jaccard(SOURCE_ESSAY, UNRELATED_ESSAY)
        self.assertGreater(sim_high, 0.4)
        self.assertLess(sim_low, 0.1)

    def test_remove_document(self):
        self.index.remove_document("source_1")
        self.assertFalse(self.index.has_document("source_1"))
        candidates = self.index.query_candidates(EXACT_COPY_ESSAY)
        self.assertNotIn("source_1", candidates)


class TestSemanticSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sem_index = SemanticIndex(device="cpu")
        cls.sem_index.index_document("source_essay", SOURCE_ESSAY)
        cls.sem_index.index_document("unrelated_essay", UNRELATED_ESSAY)

    def test_chunking_word_bounds(self):
        chunks = create_semantic_chunks(SOURCE_ESSAY, min_words=20, max_words=200)
        self.assertGreater(len(chunks), 0)
        for c in chunks:
            self.assertGreaterEqual(c.n_words, 20)
            self.assertLessEqual(c.n_words, 200)
            self.assertEqual(c.text, SOURCE_ESSAY[c.start_char : c.end_char])

    def test_paraphrase_similarity_threshold(self):
        matches = self.sem_index.search_text(PARAPHRASED_ESSAY, min_similarity=0.59)
        self.assertGreater(len(matches), 0)
        # Should match source_essay with high/medium similarity (>= 0.75)
        source_matches = [m for m in matches if m.matched_doc_id == "source_essay"]
        self.assertGreater(len(source_matches), 0)
        top_match = max(source_matches, key=lambda m: m.similarity)
        self.assertGreaterEqual(top_match.similarity, 0.75)
        self.assertIn(top_match.severity, ["medium", "high"])

    def test_unrelated_has_low_similarity(self):
        matches = self.sem_index.search_text(UNRELATED_ESSAY, min_similarity=0.75)
        source_matches = [m for m in matches if m.matched_doc_id == "source_essay"]
        self.assertEqual(len(source_matches), 0)

    def test_severity_classification(self):
        self.assertEqual(classify_severity(0.95), "high")
        self.assertEqual(classify_severity(0.80), "medium")
        self.assertEqual(classify_severity(0.65), "low")
        self.assertEqual(classify_severity(0.40), "none")


class TestSimilarityAggregator(unittest.TestCase):
    def test_no_double_counting(self):
        # Create an exact span and a paraphrase span covering the same range
        text = "This is a sample document that has exactly ten words."
        exact_spans = {
            "src_1": [ExactMatchSpan(doc_a_start=0, doc_a_end=25, doc_b_start=0, doc_b_end=25,
                                     text_a=text[:25], text_b=text[:25])]
        }
        from similarity.semantic import SemanticMatch
        # Overlapping paraphrase match covering the exact same span
        semantic_matches = [
            SemanticMatch(
                query_start_char=0,
                query_end_char=25,
                query_text=text[:25],
                matched_doc_id="src_1",
                matched_start_char=0,
                matched_end_char=25,
                matched_text=text[:25],
                similarity=0.88,
                severity="medium",
            )
        ]

        report = aggregate_similarity(text, exact_spans, semantic_matches, min_paraphrase_similarity=0.75)
        # Verify matched_words does not double count words
        word_count = len(text.split())
        self.assertLessEqual(report.matched_words, word_count)
        self.assertAlmostEqual(report.total_similarity_pct, report.exact_similarity_pct)
        self.assertEqual(report.paraphrase_similarity_pct, 0.0)  # exact took precedence

    def test_dolos_fragment_export(self):
        text = "Alpha beta gamma delta epsilon zeta eta theta."
        exact_spans = {
            "doc_b": [ExactMatchSpan(doc_a_start=0, doc_a_end=10, doc_b_start=0, doc_b_end=10,
                                     text_a=text[:10], text_b=text[:10])]
        }
        report = aggregate_similarity(text, exact_spans, [])
        d = report.to_dict()
        self.assertIn("total_similarity_pct", d)
        self.assertIn("sources_breakdown", d)
        self.assertIn("merged_fragments", d)
        self.assertGreater(len(d["sources_breakdown"]), 0)
        self.assertEqual(d["sources_breakdown"][0]["source_id"], "doc_b")


class TestEndToEndPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1. Initialize indices
        cls.lsh = MinHashIndex(threshold=0.2, num_perm=128)
        cls.semantic = SemanticIndex(device="cpu")

        # 2. Archive source document
        cls.doc_id = "essay_archive_001"
        cls.lsh.index_document(cls.doc_id, SOURCE_ESSAY)
        cls.semantic.index_document(cls.doc_id, SOURCE_ESSAY)

    def run_pipeline(self, query_text: str) -> AggregatedSimilarityReport:
        # Step A: LSH candidate filtering
        candidates = self.lsh.query_candidates(query_text)

        # Step B: Winnowing exact matches against retrieved candidates
        exact_matches_by_source: dict[str, list[ExactMatchSpan]] = {}
        for cand_id in candidates:
            # In a real system, look up cand_id text from DB/archive
            cand_text = SOURCE_ESSAY if cand_id == self.doc_id else ""
            spans = find_exact_matches(query_text, cand_text, k=5, window_size=4)
            if spans:
                exact_matches_by_source[cand_id] = spans

        # Step C: Semantic search in FAISS
        semantic_matches = self.semantic.search_text(query_text, min_similarity=0.59)

        # Step D: Unified aggregation
        return aggregate_similarity(query_text, exact_matches_by_source, semantic_matches)

    def test_e2e_exact_copy(self):
        report = self.run_pipeline(EXACT_COPY_ESSAY)
        # Should detect significant exact match percentage
        self.assertGreaterEqual(report.total_similarity_pct, 60.0)
        self.assertGreaterEqual(report.exact_similarity_pct, 60.0)
        self.assertGreater(len(report.sources_breakdown), 0)
        self.assertEqual(report.sources_breakdown[0].source_id, self.doc_id)

    def test_e2e_paraphrase(self):
        report = self.run_pipeline(PARAPHRASED_ESSAY)
        # Paraphrase should yield significant paraphrase similarity
        self.assertGreaterEqual(report.total_similarity_pct, 50.0)
        self.assertGreaterEqual(report.paraphrase_similarity_pct, 50.0)

    def test_e2e_unrelated(self):
        report = self.run_pipeline(UNRELATED_ESSAY)
        # Unrelated text must yield 0% similarity against archive
        self.assertEqual(report.total_similarity_pct, 0.0)
        self.assertEqual(report.matched_words, 0)
        self.assertEqual(len(report.sources_breakdown), 0)


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
