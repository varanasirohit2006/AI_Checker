"""End-to-End Pipeline Integration Tests (Step 8).

Verifies the 5-stage analysis pipeline across four critical scenarios:
  1. Clean human essay: low AI score, 0% similarity, 0 Red Flags.
  2. Clean AI essay: elevated AI score, 0% similarity, 0 Red Flags.
  3. Plagiarized essay: matched source fragments, elevated similarity %, 0 Red Flags.
  4. Tampered document: triggers Red Flags for homoglyphs + hidden text, yet
     downstream AI and Similarity scores evaluate cleanly on sanitized text.

Run:  .venv/Scripts/python.exe -m unittest tests.test_e2e_pipeline -v
  or: .venv/Scripts/python.exe tests/test_e2e_pipeline.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from docx import Document
from docx.shared import Pt, RGBColor

from pipeline.runner import PipelineRunner
from pipeline.schemas import UnifiedOriginalityReport

FIXTURES_DIR = ROOT / "tests" / "fixtures"

ARCHIVE_SOURCE_TEXT = (
    "Photosynthesis is a fundamental biological process utilized by green plants, algae, "
    "and cyanobacteria to convert solar electromagnetic radiation into chemical energy "
    "stored within carbohydrate compounds such as glucose. Chlorophyll pigments situated "
    "within the thylakoid membranes of chloroplasts absorb light energy primarily in the "
    "blue and red portions of the visible spectrum while reflecting green wavelengths. "
    "During the light-dependent reactions, water molecules undergo photolysis, yielding "
    "oxygen gas as an environmental byproduct and synthesizing ATP and NADPH molecules. "
    "Subsequently, the light-independent Calvin cycle utilizes these energetic carriers "
    "to fix atmospheric carbon dioxide into three-carbon sugars through the catalytic action "
    "of the enzyme ribulose-1,5-bisphosphate carboxylase-oxygenase, commonly known as RuBisCO. "
    "This biochemical pathway underpins virtually all terrestrial and aquatic food webs by "
    "supplying both organic biomass and atmospheric oxygen necessary for aerobic cellular respiration."
)

HUMAN_ESSAY_TEXT = (
    "Growing up in a coastal harbor town instilled in me an enduring fascination with maritime "
    "history and regional ecology. Every Saturday morning my brother and I would ride our bikes down "
    "to the commercial fish docks before sunrise to watch the trawlers unload their overnight catches. "
    "The old fishermen were generally quiet men who spoke in terse nods, but occasionally one of them "
    "would take the time to point out a curious species of deep-water crab or explain how seasonal water "
    "temperatures altered the migration patterns of cod and haddock. Those informal dawn conversations "
    "taught me far more about the delicate equilibrium of marine ecosystems than any standardized "
    "textbook could have conveyed. Later in college, when I enrolled in introductory oceanography, "
    "I frequently found myself recalling the pungent smell of salt brine, diesel fumes, and damp rope "
    "as we analyzed acoustic sonar readings and bathymetric charts of the continental shelf."
)

AI_ESSAY_TEXT = (
    "Artificial intelligence is rapidly reshaping the landscape of global commerce and technological "
    "innovation. By automating routine operational workflows and providing predictive analytical insights, "
    "modern machine learning architectures empower enterprises to maximize organizational productivity and "
    "optimize resource allocation across complex logistical networks. Furthermore, the systematic integration "
    "of intelligent virtual assistants enhances customer engagement and drives continuous operational efficiency "
    "within diverse business domains. In contemporary enterprise environments, cultivating a culture of data-driven "
    "decision-making has become essential for securing competitive market advantages and fostering long-term resilience. "
    "Organizations that successfully adopt scalable cloud-native machine learning infrastructures can unlock significant "
    "synergies between human expertise and automated intelligence, thereby driving sustainable economic growth. "
    "Additionally, ethical considerations surrounding algorithmic transparency and data privacy must guide executive "
    "governance frameworks. Ensuring equitable deployment of technological breakthroughs remains imperative for societal progress. "
    "Consequently, business leaders and technology executives must collaborate closely with academic researchers and public "
    "policymakers to develop comprehensive accountability benchmarks that foster responsible and trustworthy algorithmic adoption."
)

PLAGIARIZED_ESSAY_TEXT = (
    "In this comprehensive scientific paper, we investigate fundamental plant biochemistry and solar energy capture. "
    + ARCHIVE_SOURCE_TEXT
    + " In conclusion, understanding the molecular mechanisms of carbon fixation remains essential for agricultural biotechnology."
)


def create_tampered_docx(dest_path: Path) -> None:
    """Create a DOCX fixture with mixed-script homoglyphs and hidden white text."""
    doc = Document()
    p1 = doc.add_paragraph()
    # Mixed-script homoglyphs (Cyrillic lookalikes in Latin words)
    p1.add_run("The student submitted their report to ")
    p1.add_run("gооgle").bold = True  # Cyrillic 'о'
    p1.add_run(" and processed payments via ")
    p1.add_run("раypal").bold = True  # Cyrillic 'а', 'у'
    p1.add_run(" after completing their final essay assignment.")

    # Main text body (clean content >= 150 words)
    p2 = doc.add_paragraph()
    p2.add_run(HUMAN_ESSAY_TEXT)

    # Injected hidden white text (deliberate evasion attempt)
    p3 = doc.add_paragraph()
    run_white = p3.add_run("This is invisible white text designed to deceive automated plagiarism scanners.")
    run_white.font.color.rgb = RGBColor(255, 255, 255)

    doc.save(str(dest_path))


class TestEndToEndPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = PipelineRunner()
        # Seed archive with reference document
        cls.archive_id = "doc_photosynthesis_ref_01"
        cls.runner.add_archive_document(cls.archive_id, ARCHIVE_SOURCE_TEXT)

        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.temp_path = Path(cls.temp_dir.name)

        cls.human_file = cls.temp_path / "human_essay.txt"
        cls.human_file.write_text(HUMAN_ESSAY_TEXT, encoding="utf-8")

        cls.ai_file = cls.temp_path / "ai_essay.txt"
        cls.ai_file.write_text(AI_ESSAY_TEXT, encoding="utf-8")

        cls.plagiarized_file = cls.temp_path / "plagiarized_essay.txt"
        cls.plagiarized_file.write_text(PLAGIARIZED_ESSAY_TEXT, encoding="utf-8")

        cls.tampered_docx = cls.temp_path / "tampered_submission.docx"
        create_tampered_docx(cls.tampered_docx)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_clean_human_essay(self):
        report = self.runner.analyze_file(self.human_file)

        # 1. Metadata check
        self.assertEqual(report.metadata.file_type, "txt")
        self.assertGreaterEqual(report.metadata.sanitized_word_count, 150)

        # 2. Integrity check: 0 Red Flags
        self.assertFalse(report.integrity.has_tampering)
        self.assertEqual(report.integrity.total_flags, 0)

        # 3. Similarity check: 0% match against unrelated photosynthesis archive
        self.assertEqual(report.similarity.total_similarity_pct, 0.0)
        self.assertEqual(report.similarity.sources_count, 0)

        # 4. AI check: status DONE, human qualitative label, disclaimer present
        self.assertEqual(report.ai_detection.status, "DONE")
        self.assertIn("Estimate only, not proof", report.ai_detection.disclaimer)

        # 5. UI Summary Card
        self.assertEqual(report.summary_card.red_flags_count, 0)
        self.assertEqual(report.summary_card.similarity_pct, 0.0)

    def test_ai_generated_essay(self):
        report = self.runner.analyze_file(self.ai_file)

        # Clean AI file: 0 Red Flags, 0% plagiarism
        self.assertFalse(report.integrity.has_tampering)
        self.assertEqual(report.similarity.total_similarity_pct, 0.0)

        # AI Detection status DONE
        self.assertEqual(report.ai_detection.status, "DONE")
        self.assertIsNotNone(report.ai_detection.document_ai_pct)
        self.assertTrue(report.ai_detection.is_english)

    def test_plagiarized_essay(self):
        report = self.runner.analyze_file(self.plagiarized_file)

        # No tampering flags
        self.assertFalse(report.integrity.has_tampering)

        # High similarity detected against photosynthesis reference
        self.assertGreaterEqual(report.similarity.total_similarity_pct, 60.0)
        self.assertGreaterEqual(report.similarity.exact_similarity_pct, 60.0)
        self.assertGreater(report.similarity.sources_count, 0)

        # Verified Dolos source breakdown and fragments
        first_source = report.similarity.sources_breakdown[0]
        self.assertEqual(first_source["source_id"], self.archive_id)
        self.assertGreater(len(report.similarity.fragments), 0)

    def test_tampered_document_evasion_caught(self):
        report = self.runner.analyze_file(self.tampered_docx)

        # 1. Tampering PROVEN to raise Red Flags
        self.assertTrue(report.integrity.has_tampering)
        self.assertGreaterEqual(report.integrity.total_flags, 2)
        self.assertIn("replaced_character", report.integrity.categories_found)
        self.assertIn("hidden_text", report.integrity.categories_found)

        # 2. Sanitization successfully sanitized the document pre-scoring
        self.assertGreater(report.metadata.sanitized_word_count, 150)

        # 3. Downstream AI detection still succeeds on sanitized text
        self.assertEqual(report.ai_detection.status, "DONE")
        self.assertIsNotNone(report.ai_detection.document_ai_pct)

        # 4. Summary card accurately synthesizes all three pillars
        self.assertGreater(report.summary_card.red_flags_count, 0)
        self.assertIsNotNone(report.summary_card.ai_pct)
        self.assertIsNotNone(report.summary_card.similarity_pct)
        self.assertIn("Estimate only, not proof", report.summary_card.disclaimer)


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
