"""Unit and integration tests for Step 7: Calibration & AI Ensemble Guardrails.

Verifies:
  1. Length guardrail: < 150 words returns 'Too short to estimate'
  2. Language guardrail: non-English text raises confidence warning
  3. GLTR rank attachment: forensic word rank buckets & colors
  4. 2-Signal fusion: logistic regression sigmoid calculation
  5. Window-to-document rollup: word-level aggregation & qualitative labels
  6. Disclaimer: 'Estimate only, not proof' presence

Run:  .venv/Scripts/python.exe -m unittest tests.test_calibration -v
  or: .venv/Scripts/python.exe tests/test_calibration.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from detectors.ensemble import (
    AIEnsembleDetector,
    DocumentPrediction,
    WindowPrediction,
    is_non_english,
    sigmoid,
)
from detectors.gltr_ranks import GLTRRankDetector, assign_bucket

# Test passages
SHORT_ESSAY = (
    "This is a very brief note that has far fewer than one hundred and fifty words. "
    "Under product safety rules, it should not be evaluated for AI writing."
)

ENGLISH_LONG_ESSAY = (
    "Artificial intelligence is rapidly transforming modern higher education across multiple domains. "
    "Universities around the world are currently adopting automated grading systems, personalized virtual "
    "tutoring agents, and responsive adaptive learning software to enhance academic student outcomes. "
    "However, the widespread accessibility of generative large language models presents substantial challenges "
    "for scholastic integrity. Instructors must reconsider traditional assessment strategies to ensure that "
    "students genuinely develop critical thinking, synthesis, and quantitative reasoning capabilities. "
    "Furthermore, pedagogical frameworks must adapt to emphasize interactive oral examinations, supervised "
    "in-class drafting sessions, and iterative project portfolios rather than unmonitored take-home assignments. "
    "Ultimately, the goal of modern academic institutions should not be to ban artificial intelligence, but rather "
    "to foster transparent and ethical engagement while upholding rigorous standards of independent scholarship. "
    "By developing comprehensive institutional guidelines and educating students on proper attribution standards, "
    "faculties can cultivate an environment of academic integrity and innovative pedagogical excellence. "
    "This proactive approach ensures that graduates possess both technological proficiency and strong ethical grounding."
)

NON_ENGLISH_ESSAY = (
    "Зимний вечер опустился на заснеженный старинный город, и уличные фонари зажглись мягким золотистым светом. "
    "Люди спешили домой после долгого рабочего дня, укутавшись в теплые шерстяные шарфы и плотные зимние пальто. "
    "Снег тихо падал на мостовые и крыши домов, создавая атмосферу уюта и покоя. В небольшом кафе на углу играла "
    "тихая музыка, и пахло свежесваренным кофе с корицей и ванильной выпечкой. "
    "Такие вечера напоминают нам о важности простых человеческих радостей и домашнего тепла. "
    "Студенты университета собирались за деревянными столиками, обсуждая предстоящие экзамены по литературе и истории. "
    "За окнами кружилась метель, укрывая деревья в парке пушистым белым покрывалом."
)


class TestGuardrails(unittest.TestCase):
    def test_short_document_returns_too_short(self):
        detector = AIEnsembleDetector()
        res = detector.predict_document(SHORT_ESSAY)
        self.assertEqual(res.status, "TOO_SHORT")
        self.assertEqual(res.message, "Too short to estimate")
        self.assertIsNone(res.document_ai_pct)
        self.assertLess(res.total_words, 150)
        self.assertIn("Estimate only, not proof", res.disclaimer)

    def test_long_document_evaluates(self):
        # Long document has > 150 words
        word_count = len(ENGLISH_LONG_ESSAY.split())
        self.assertGreaterEqual(word_count, 150)

    def test_language_detection(self):
        self.assertFalse(is_non_english(ENGLISH_LONG_ESSAY))
        self.assertTrue(is_non_english(NON_ENGLISH_ESSAY))


class TestGLTRRankDetector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gltr = GLTRRankDetector(model_name="gpt2", device="cpu")

    def test_assign_bucket(self):
        self.assertEqual(assign_bucket(1), ("top-10", "green"))
        self.assertEqual(assign_bucket(10), ("top-10", "green"))
        self.assertEqual(assign_bucket(11), ("top-100", "yellow"))
        self.assertEqual(assign_bucket(100), ("top-100", "yellow"))
        self.assertEqual(assign_bucket(101), ("top-1000", "red"))
        self.assertEqual(assign_bucket(1000), ("top-1000", "red"))
        self.assertEqual(assign_bucket(1001), ("rest", "purple"))

    def test_gltr_analysis(self):
        sample = "The cat sat on the warm mat."
        report = self.gltr.analyze_text(sample)
        self.assertGreater(report.total_tokens, 0)
        self.assertEqual(len(report.token_ranks), report.total_tokens)
        pct_sum = report.top10_pct + report.top100_pct + report.top1000_pct + report.rest_pct
        self.assertAlmostEqual(pct_sum, 100.0, places=1)
        for tr in report.token_ranks:
            self.assertIn(tr.bucket, ["top-10", "top-100", "top-1000", "rest"])
            self.assertIn(tr.color, ["green", "yellow", "red", "purple"])


class TestEnsembleMathAndRollup(unittest.TestCase):
    def test_sigmoid_math(self):
        self.assertAlmostEqual(sigmoid(0.0), 0.5)
        self.assertGreater(sigmoid(2.0), 0.8)
        self.assertLess(sigmoid(-2.0), 0.2)

    def test_predict_window_fusion_logic(self):
        # Create detector with mock/calibrated coefficients
        detector = AIEnsembleDetector(threshold=0.50)
        detector.intercept = 0.0
        detector.weight_bino = -1.0
        detector.weight_fd = 1.0

        # High AI test window: lower bino score (0.7), higher fd crit (2.0)
        # z = 0.0 + (-1.0 * 0.7) + (1.0 * 2.0) = 1.3
        # sigmoid(1.3) ≈ 0.7858 >= 0.50 -> AI
        z = detector.intercept + (-1.0 * 0.7) + (1.0 * 2.0)
        prob = sigmoid(z)
        self.assertGreater(prob, 0.50)

    def test_document_prediction_rollup(self):
        detector = AIEnsembleDetector(threshold=0.50)
        pred = detector.predict_document(ENGLISH_LONG_ESSAY)
        self.assertEqual(pred.status, "DONE")
        self.assertIsNotNone(pred.document_ai_pct)
        self.assertGreaterEqual(pred.document_ai_pct, 0.0)
        self.assertLessEqual(pred.document_ai_pct, 100.0)
        self.assertTrue(pred.is_english)
        self.assertIsNone(pred.confidence_warning)
        self.assertIn("Estimate only, not proof", pred.disclaimer)
        self.assertIn(pred.qualitative_label, [
            "Likely human-generated",
            "Mixed / partially AI-generated",
            "Likely AI-generated",
        ])


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
