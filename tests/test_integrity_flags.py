"""Step 6 gate — integrity flags, sanitization, parsing, chunking.

Pass conditions (AGENTS.md §4 step 6 / §6A):
  * >= 99% recall on injected tamper instances (tests/fixtures/manifest.json)
  * 0 false positives on benign styled cover pages, dark banners, shaded
    tables, and pure non-Latin documents

Run:  .venv/Scripts/python.exe -m unittest tests.test_integrity_flags -v
  or: .venv/Scripts/python.exe tests/test_integrity_flags.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ingest import chunker, flags, parser
from ingest.sanitizer import sanitize

FIXTURES = ROOT / "tests" / "fixtures"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))


def matching_instances(file_flags: list, entry: dict) -> list:
    out = []
    for fl in file_flags:
        if fl.category != entry["category"] or fl.kind != entry["kind"]:
            continue
        if not all(fl.location.get(k) == v for k, v in entry["locator"].items()):
            continue
        for inst in fl.instances:
            if entry["key"] is None:
                out.append(inst)
            elif entry["category"] == "replaced_character" and inst.get("word") == entry["key"]:
                out.append(inst)
            elif entry["category"] == "hidden_unicode" and inst.get("codepoint") == entry["key"]:
                out.append(inst)
            elif entry["category"] == "hidden_text" and inst.get("text") == entry["key"]:
                out.append(inst)
    return out


class TestIntegrityFlags(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.flags_by_file = {}
        for entry in MANIFEST["tampered"]:
            name = entry["file"]
            if name not in cls.flags_by_file:
                cls.flags_by_file[name] = flags.inspect_file(FIXTURES / name)

    def test_tamper_recall_at_least_99_percent(self):
        expected = matched = 0
        misses = []
        for entry in MANIFEST["tampered"]:
            found = len(matching_instances(self.flags_by_file[entry["file"]], entry))
            hit = min(found, entry["count"])
            expected += entry["count"]
            matched += hit
            if hit < entry["count"]:
                misses.append(f"{entry['file']} {entry['category']}/{entry['kind']} "
                              f"key={entry['key']} locator={entry['locator']} "
                              f"{hit}/{entry['count']}")
        recall = matched / expected
        print(f"\n  tamper recall: {matched}/{expected} = {recall:.4f}")
        self.assertGreaterEqual(recall, 0.99, msg="misses:\n" + "\n".join(misses))

    def test_zero_false_positives_on_benign_fixtures(self):
        for name in MANIFEST["benign"]:
            with self.subTest(fixture=name):
                found = flags.inspect_file(FIXTURES / name)
                self.assertEqual(found, [], msg=f"{name}: {[f.summary() for f in found]}")

    def test_all_three_categories_present(self):
        categories = {fl.category for f in self.flags_by_file.values() for fl in f}
        self.assertEqual(categories, {flags.REPLACED_CHARACTER, flags.HIDDEN_UNICODE,
                                      flags.HIDDEN_TEXT})

    def test_grouping_per_paragraph(self):
        fl = self.flags_by_file["tampered_homoglyphs.docx"]
        self.assertEqual(len(fl), 3)  # one grouped flag per paragraph
        self.assertTrue(all(f.count == 4 for f in fl))

    def test_pure_cyrillic_not_flagged_but_mixed_is(self):
        self.assertEqual(flags.scan_text("привет мир"), [])
        self.assertTrue(flags.scan_text("раypal"))


class TestSanitizer(unittest.TestCase):
    def test_strips_hidden_and_maps_homoglyphs(self):
        text = "Please visit раypal\u200b and gооgle\u00ad soon. привет мир"
        result = sanitize(text)
        self.assertNotIn("\u200b", result.text)
        self.assertNotIn("\u00ad", result.text)
        self.assertIn("paypal", result.text)
        self.assertIn("google", result.text)
        self.assertIn("привет мир", result.text)  # pure Cyrillic untouched
        kinds = {c["type"] for c in result.changes}
        self.assertEqual(kinds, {"removed", "homoglyph"})

    def test_clean_text_unchanged(self):
        text = "A perfectly ordinary English sentence."
        result = sanitize(text)
        self.assertEqual(result.text, text)
        self.assertFalse(result.changed)

    def test_sanitized_tampered_fixture_has_no_character_flags(self):
        doc = parser.parse(FIXTURES / "tampered_homoglyphs.docx")
        clean = sanitize(doc.text).text
        self.assertEqual(flags.scan_text(clean), [])
        doc = parser.parse(FIXTURES / "tampered_zero_width.docx")
        clean = sanitize(doc.text).text
        self.assertEqual(flags.scan_text(clean), [])


class TestParser(unittest.TestCase):
    def test_docx_references_stripped(self):
        doc = parser.parse(FIXTURES / "benign_clean.docx")
        self.assertNotIn("References", doc.text)
        self.assertNotIn("Smith", doc.text)
        self.assertIn("committee", doc.text)

    def test_pdf_header_footer_stripped(self):
        doc = parser.parse(FIXTURES / "benign_clean.pdf")
        self.assertEqual(doc.n_pages, 3)
        self.assertNotIn("ACME UNIVERSITY", doc.text)
        self.assertNotIn("Originality Checker Sample", doc.text)
        self.assertNotIn("References", doc.text)
        self.assertIn("committee", doc.text)

    def test_txt(self):
        tmp = FIXTURES / "_tmp_test.txt"
        tmp.write_text("First paragraph.\n\nSecond paragraph.\n", encoding="utf-8")
        try:
            doc = parser.parse(tmp)
            self.assertEqual(len(doc.paragraphs), 2)
        finally:
            tmp.unlink()


class TestChunker(unittest.TestCase):
    def test_sentence_split(self):
        text = "Hello world. This is fine! Really? Yes it is."
        sents = chunker.split_sentences(text)
        self.assertEqual(len(sents), 4)
        self.assertEqual(sents[0].text, "Hello world.")
        self.assertEqual(text[sents[1].start:sents[1].end], sents[1].text)

    def test_windows_250_words_50pct_overlap(self):
        sentence = "The quick brown fox jumps over the lazy dog again today. "
        text = sentence * 60  # 60 sentences x 11 words = 660 words
        windows = chunker.chunk(text)
        self.assertGreaterEqual(len(windows), 3)
        for w in windows[:-1]:
            self.assertGreaterEqual(w.n_words, 250)
        for w in windows:
            self.assertEqual(text[w.start_char:w.end_char], w.text)
        self.assertEqual(windows[0].start_char, 0)
        self.assertEqual(windows[-1].end_char, len(text))
        sents = chunker.split_sentences(text)
        for a, b in zip(windows, windows[1:]):
            shared = sum(sents[i].n_words
                         for i in range(b.first_sentence, a.last_sentence + 1))
            frac = shared / a.n_words
            self.assertGreaterEqual(frac, 0.30)
            self.assertLessEqual(frac, 0.70)
            self.assertGreater(b.first_sentence, a.first_sentence)

    def test_short_text_single_window(self):
        windows = chunker.chunk("One short sentence here.")
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0].text, "One short sentence here.")

    def test_empty(self):
        self.assertEqual(chunker.chunk(""), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)