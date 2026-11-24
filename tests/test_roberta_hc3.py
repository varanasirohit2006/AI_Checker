"""Tests for RoBERTa HC3 Detector & 3-Signal Ensemble Fusion (Step 12).

Verifies:
  1. RobertaHC3Detector scoring structure and probability outputs.
  2. Fallback heuristic resilience when network is disconnected / offline.
  3. 3-signal fusion integration in AIEnsembleDetector.

Run: .venv/Scripts/python.exe tests/test_roberta_hc3.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from detectors.ensemble import AIEnsembleDetector
from detectors.roberta_hc3 import RobertaHC3Detector


class TestRobertaHC3(unittest.TestCase):
    def test_01_roberta_scoring_structure(self):
        detector = RobertaHC3Detector(force_fallback=True)
        res = detector.score_text("This is an ordinary human student sentence written for an assignment.")
        self.assertIn("ai_probability", res)
        self.assertIn("human_probability", res)
        self.assertIn("predicted_label", res)
        self.assertGreaterEqual(res["ai_probability"], 0.0)
        self.assertLessEqual(res["ai_probability"], 1.0)
        self.assertAlmostEqual(res["ai_probability"] + res["human_probability"], 1.0, places=3)

    def test_02_empty_text_handling(self):
        detector = RobertaHC3Detector(force_fallback=True)
        res = detector.score_text("")
        self.assertEqual(res["ai_probability"], 0.0)
        self.assertEqual(res["predicted_label"], "human")

    def test_03_three_signal_ensemble_fusion(self):
        roberta = RobertaHC3Detector(force_fallback=True)
        detector = AIEnsembleDetector(roberta=roberta, enable_roberta=True)
        self.assertTrue(detector.enable_roberta)

        sample = (
            "The technology is based on a process called deep learning, which allows computers to learn from vast amounts "
            "of data and identify patterns. This technology has been used in a wide range of applications, including image recognition, "
            "speech recognition, and natural language processing. In recent years, deep learning has achieved remarkable results in many domains, "
            "surpassing human performance in tasks such as image classification and game playing."
        )
        pred = detector.predict_window(sample)
        self.assertGreaterEqual(pred.fused_probability, 0.0)
        self.assertLessEqual(pred.fused_probability, 1.0)


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
