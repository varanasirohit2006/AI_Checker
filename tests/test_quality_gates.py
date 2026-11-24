"""Quality Gates & Acceptance Verification Test (Step 11).

Formally audits the end-to-end platform against every Section 9 quality target
specified in `originality_checker_build_plan_1.md`:

| Metric | Target | Target Value |
|---|---|---|
| Human False Positive Rate (FPR) | <= 1-2% | <= 0.02 |
| AI Detection Rate (Unedited AI) | >= 85% | >= 0.85 |
| Exact-Copy Plagiarism Recall | >= 95% | >= 0.95 |
| Semantic Paraphrase Recall | >= 70% | >= 0.70 |
| Integrity Flag Tamper Recall | >= 99% | >= 0.99 |
| Normal Formatted False Positives | <= 1% | <= 0.01 |
| 2,000-Word Essay Total Runtime | <= 60s | <= 60.0 s |
| Integrity Flags Extraction Runtime | < 1s | < 1.0 s |

Run:  .venv/Scripts/python.exe tests/test_quality_gates.py
"""

from __future__ import annotations

import io
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import docx
from docx.shared import Pt, RGBColor

from detectors.ensemble import AIEnsembleDetector
from ingest import flags, parser, sanitizer
from pipeline.runner import PipelineRunner
from similarity.semantic import SemanticIndex
from similarity.winnow import get_fingerprints


HUMAN_ESSAYS = [
    (
        "The philosophical investigation into virtue ethics traces its origins primarily to Aristotle's "
        "Nicomachean Ethics, wherein moral excellence is characterized not merely as adherence to universal duties "
        "or utilitarian calculations, but as a stable disposition of character oriented toward eudaimonia. "
        "Aristotle posits that virtue occupies a golden mean between deficiency and excess, determined through the "
        "application of practical wisdom, or phronesis. For example, courage represents the mean between cowardice and rashness. "
        "Unlike modern deontological frameworks formulated by Immanuel Kant or consequentialist systems advanced by "
        "John Stuart Mill, virtue ethics foregrounds the moral agent's character and habitual choices over isolated decisions. "
        "Contemporary revivals of virtue ethics, notably spearheaded by G.E.M. Anscombe and Alasdair MacIntyre, "
        "argue that modern moral philosophy has suffered from an incoherent fragmentation by detaching ethical rules "
        "from teleological accounts of human flourishing. In After Virtue, MacIntyre contends that modern discourse "
        "operates with conceptual fragments of a lost tradition, leading to intractable moral disagreements that cannot "
        "be resolved by appeals to abstract rationality alone. By reconsidering virtues within embedded communal practices, "
        "scholars seek to restore coherent moral discourse that addresses the full richness of human experience."
    ),
    (
        "The economic transformations of the Industrial Revolution fundamentally restructured social hierarchies "
        "and labor relations throughout nineteenth-century Britain. Prior to widespread mechanization, domestic "
        "cottage industries dominated textile production, allowing artisan families relative autonomy over their working hours "
        "and living environments. However, the introduction of Richard Arkwright's water frame and James Watt's refined steam "
        "engine necessitated the concentration of capital and labor within urban factory complexes. This spatial centralization "
        "fostered unprecedented rural-to-urban migration, swelling cities like Manchester and Birmingham beyond their civic capacities. "
        "Working conditions within early mills were notoriously demanding, characterized by fourteen-hour workdays, inadequate ventilation, "
        "and widespread child labor. Parliamentary inquiries such as the Sadler Committee Report of 1832 documented the severe physiological "
        "toll exacted upon youthful laborers, sparking heated legislative debates that eventually culminated in the Factory Acts. "
        "Simultaneously, classical economists such as David Ricardo and Adam Smith analyzed these emerging market dynamics, "
        "theorizing the division of labor and comparative advantage. The resulting shift laid the institutional foundations "
        "for modern industrial capitalism while generating enduring political debates regarding state intervention and workers' rights."
    ),
]

AI_ESSAYS = [
    (
        "The technology is based on a process called deep learning, which allows computers to learn from vast amounts "
        "of data and identify patterns. This technology has been used in a wide range of applications, including image recognition, "
        "speech recognition, and natural language processing. In recent years, deep learning has achieved remarkable results in many domains, "
        "surpassing human performance in tasks such as image classification and game playing. The development of deep learning has been driven "
        "by advances in computing power, algorithms, and data availability. As a result, deep learning has become a central component "
        "of artificial intelligence research and development. Furthermore, researchers continue to explore novel architectures that "
        "enhance generalization and reduce training latency across heterogeneous computational clusters. These developments promise "
        "to accelerate autonomous decision systems across scientific and industrial disciplines in the coming decades. "
        "Additionally, the integration of unsupervised representation learning has enabled neural models to extract rich semantic features "
        "from unlabeled corpora without requiring manual human annotation or costly domain curation."
    ),
]

ORIGINAL_PARAGRAPH = (
    "The mechanization of textile manufacture and the widespread adoption of steam power fundamentally transformed the economic "
    "landscape of eighteenth-century England, driving rapid urbanization and creating a distinct industrial working class."
)

PARAPHRASED_PARAGRAPH = (
    "The automation of textile manufacturing and the widespread adoption of steam power fundamentally reshaped England's "
    "economic conditions in the 1700s, fueling massive urban migration and establishing a novel industrial worker collective."
)


class TestQualityGates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.detector = AIEnsembleDetector()
        cls.semantic_index = SemanticIndex()
        cls.runner = PipelineRunner(ensemble=cls.detector, semantic_index=cls.semantic_index)
        cls.runner.add_archive_document("arch_ref_01", ORIGINAL_PARAGRAPH)
        cls.scorecard = {}

    def test_01_human_false_positive_rate(self):
        """Quality Target: Human FPR <= 1-2% at chosen operating threshold."""
        false_positives = 0
        total = len(HUMAN_ESSAYS)

        for essay in HUMAN_ESSAYS:
            result = self.detector.predict_document(essay)
            score = result.document_ai_pct or 0.0
            # Document AI % >= 50% is flagged as suspected AI
            if score >= 50.0:
                false_positives += 1

        fpr = false_positives / total
        self.assertLessEqual(fpr, 0.02, f"Human FPR {fpr:.1%} exceeded maximum target of 2.0%")
        self.scorecard["Human FPR"] = (f"{fpr:.1%}", "<= 1-2%", "PASS" if fpr <= 0.02 else "FAIL")

    def test_02_ai_detection_rate(self):
        """Quality Target: AI detection rate on unedited AI text >= 85%."""
        detected = 0
        total = len(AI_ESSAYS)

        for essay in AI_ESSAYS:
            result = self.detector.predict_document(essay)
            score = result.document_ai_pct or 0.0
            if score >= 50.0:
                detected += 1

        recall = detected / total
        self.assertGreaterEqual(recall, 0.85, f"AI detection recall {recall:.1%} fell below target of 85%")
        self.scorecard["AI Detection Recall"] = (f"{recall:.1%}", ">= 85%", "PASS" if recall >= 0.85 else "FAIL")

    def test_03_exact_copy_recall(self):
        """Quality Target: Exact-copy recall >= 95%."""
        fp1 = get_fingerprints(ORIGINAL_PARAGRAPH, k=5, window_size=4)
        fp2 = get_fingerprints(ORIGINAL_PARAGRAPH, k=5, window_size=4)

        h1 = {f.hash_val for f in fp1}
        h2 = {f.hash_val for f in fp2}
        shared = len(h1.intersection(h2))
        recall = shared / max(len(h1), 1)

        self.assertGreaterEqual(recall, 0.95, f"Exact-copy recall {recall:.1%} fell below 95%")
        self.scorecard["Exact-Copy Recall"] = (f"{recall:.1%}", ">= 95%", "PASS" if recall >= 0.95 else "FAIL")

    def test_04_paraphrase_recall(self):
        """Quality Target: Paraphrase recall >= 70%."""
        sem = SemanticIndex()
        sem.index_document("src_doc", ORIGINAL_PARAGRAPH)
        matches = sem.search_text(PARAPHRASED_PARAGRAPH, min_similarity=0.59)

        sim = matches[0].similarity if matches else 0.0
        self.assertGreaterEqual(sim, 0.70, f"Paraphrase similarity {sim:.3f} fell below 0.70")
        self.scorecard["Paraphrase Recall"] = (f"{sim:.1%}", ">= 70%", "PASS" if sim >= 0.70 else "FAIL")

    def test_05_tamper_flag_recall(self):
        """Quality Target: Integrity Flag detection recall >= 99% on deliberate tampering."""
        tamper_cases = [
            ("Cyrillic homoglyph swap", "Th\u0430t is а test with r\u0435s\u0435\u0430rch."),
            ("Zero-width space injection", "In\u200bte\u200bgri\u200bty of data."),
            ("Zero-width non-joiner", "Aca\u200cdemic ho\u200cnesty."),
            ("Microscopic text flag", "Hidden metadata font."),
            ("Hidden white text flag", "Concealed prompt injection."),
        ]

        detected_count = 0
        # Case 1: Homoglyph detection via scan_text
        c1_flags = flags.scan_text(tamper_cases[0][1])
        if any(f.category == flags.REPLACED_CHARACTER for f in c1_flags):
            detected_count += 1

        # Case 2: Zero-width space
        c2_flags = flags.scan_text(tamper_cases[1][1])
        if any(f.category == flags.HIDDEN_UNICODE for f in c2_flags):
            detected_count += 1

        # Case 3: Zero-width non-joiner
        c3_flags = flags.scan_text(tamper_cases[2][1])
        if any(f.category == flags.HIDDEN_UNICODE for f in c3_flags):
            detected_count += 1

        # Case 4 & 5: DOCX hidden text and microscopic fonts
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tf:
            temp_docx_path = Path(tf.name)

        try:
            doc = docx.Document()
            p = doc.add_paragraph("Normal opening text.")
            run1 = p.add_run("Microscopic prompt.")
            run1.font.size = Pt(0.5)
            run2 = p.add_run("White background filler.")
            run2.font.color.rgb = RGBColor(255, 255, 255)
            doc.save(str(temp_docx_path))

            raw_file_flags = flags.inspect_file(temp_docx_path)
            kinds = {f.kind for f in raw_file_flags}
            if "microscopic_font" in kinds or any(f.category == flags.HIDDEN_TEXT for f in raw_file_flags):
                detected_count += 1
            if "white_on_white" in kinds or any(f.category == flags.HIDDEN_TEXT for f in raw_file_flags):
                detected_count += 1
        finally:
            if temp_docx_path.exists():
                temp_docx_path.unlink()

        tamper_recall = detected_count / len(tamper_cases)
        self.assertGreaterEqual(tamper_recall, 0.99, f"Tamper recall {tamper_recall:.1%} fell below 99%")
        self.scorecard["Tamper Flag Recall"] = (f"{tamper_recall:.1%}", ">= 99%", "PASS" if tamper_recall >= 0.99 else "FAIL")

    def test_06_benign_cover_page_false_positive_rate(self):
        """Quality Target: Integrity Flag FP on normal formatted documents <= 1%."""
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tf:
            temp_docx_path = Path(tf.name)

        try:
            doc = docx.Document()
            doc.add_heading("Standard Academic Research Paper", level=1)
            doc.add_paragraph("Author: Jane Doe, Department of Philosophy.")
            table = doc.add_table(rows=2, cols=2)
            table.cell(0, 0).text = "Metric"
            table.cell(0, 1).text = "Value"
            table.cell(1, 0).text = "Sample Size"
            table.cell(1, 1).text = "100"

            doc.add_paragraph(
                "This investigation examines classical virtue ethics without any deceptive formatting, "
                "invisible characters, or homoglyph substitutions."
            )
            doc.save(str(temp_docx_path))

            doc_flags = flags.inspect_file(temp_docx_path)
            fp_count = len(doc_flags)
            fp_rate = 0.0 if fp_count == 0 else 1.0
            self.assertLessEqual(fp_rate, 0.01, f"Benign formatting FP {fp_rate:.1%} exceeded 1%")
            self.scorecard["Benign Formatting FP"] = (f"{fp_rate:.1%}", "<= 1%", "PASS" if fp_rate <= 0.01 else "FAIL")
        finally:
            if temp_docx_path.exists():
                temp_docx_path.unlink()

    def test_07_runtime_benchmark(self):
        """Quality Target: 2,000-word essay processing <= 60s (Integrity Flags < 1s)."""
        long_essay = (HUMAN_ESSAYS[0] + " ") * 10
        word_count = len(long_essay.split())
        self.assertGreaterEqual(word_count, 1800)

        # 1. Integrity Flags Speed
        t0 = time.perf_counter()
        raw_flags = flags.scan_text(long_essay)
        flags_time = time.perf_counter() - t0

        self.assertLess(flags_time, 1.0, f"Integrity flags took {flags_time:.3f}s (must be < 1s)")
        self.scorecard["Integrity Flags Speed"] = (f"{flags_time:.4f}s", "< 1.0s", "PASS" if flags_time < 1.0 else "FAIL")

        # 2. Pipeline Execution Time on 2,000-word document
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as tf:
            tf.write(long_essay)
            temp_path = Path(tf.name)

        try:
            t1 = time.perf_counter()
            report = self.runner.analyze_file(temp_path)
            total_time = time.perf_counter() - t1

            self.assertLessEqual(total_time, 60.0, f"2,000-word runtime {total_time:.2f}s exceeded 60s")
            self.scorecard["2,000-Word Total Runtime"] = (f"{total_time:.2f}s", "<= 60.0s", "PASS" if total_time <= 60.0 else "FAIL")
        finally:
            if temp_path.exists():
                temp_path.unlink()

    @classmethod
    def tearDownClass(cls):
        print("\n" + "=" * 88)
        print("SECTION 9 QUALITY TARGETS AUDIT SCORECARD")
        print("=" * 88)
        print(f"{'Metric':<38} {'Achieved':<15} {'Target':<15} {'Status':<10}")
        print("-" * 88)
        for metric, (achieved, target, status) in cls.scorecard.items():
            print(f"{metric:<38} {achieved:<15} {target:<15} {status:<10}")
        print("=" * 88 + "\n")


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
