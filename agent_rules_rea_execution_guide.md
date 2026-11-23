# AGENTS.md — Execution Rules & REA Workflow Guide

> **How to use this file:** Place this file in the root of `originality-checker/` alongside `Originality_Checker_Repo_Based_Plan.md` (and copy or symlink it to `CLAUDE.md` if using Claude Code). Every AI coding agent working in this repository must read and obey both files before creating or editing any code.

---

## 1. Mission & Operating Mode

You are building the **Originality Checker** defined in `Originality_Checker_Repo_Based_Plan.md`. Your job is to implement the system cleanly in two iterations—starting strictly with **Iteration 1 (REA Core MVP)**—without cutting corners, hallucinating algorithms, or lifting unattributed code.

* **Primary Reference:** `Originality_Checker_Repo_Based_Plan.md`
* **Methodology:** `morluto/rea` ("Reverse Engineer Anything") applied to open-source source code in `research/`.
* **Execution Style:** Sequential, evidence-backed, test-gated, and human-reviewed at every Stage 4 specification.

---

## 2. Non-Negotiable Agent Guardrails

1. **One Repository at a Time:** Never attempt to scaffold or implement multiple target repositories in a single pass. Follow the exact Iteration 1 order in Section 4.
2. **Rebuild Behaviour, Do Not Lift Code:** Study the cloned source code in `research/<repo>`, document the exact math, inputs, thresholds, and edge cases, and write clean, modular code in our own files. Only reuse code directly when the license explicitly permits it and attribution is recorded in `THIRD_PARTY_LICENSES.md`.
3. **Mandatory Evidence Citations:** Every behavioural claim in `rea/<repo>/03-evidence.md` **must** include an exact file path and line number citation (e.g., `research/Binoculars/binoculars/detector.py:42-68`). Unverified guesses are forbidden.
4. **Mandatory Review Stop (Stage 4 Gate):** After generating `rea/<repo>/01-target.md` through `rea/<repo>/04-spec.md`, **STOP** and ask the user to review and approve the specification before writing any module code in `detectors/`, `similarity/`, or `web/`.
5. **Mandatory Differential Test Gate (Stage 5 Gate):** A rebuilt module is **not done** until `tests/diff_<repo>.py` runs both the original repository (in `research/<repo>`) and our rebuilt module on the exact same test inputs and confirms matching outputs within the defined tolerance. Never move to the next repository until Stage 5 passes.
6. **Direct Libraries vs. REA Rebuilds:** Do **not** waste time reverse-engineering standard installable packages (`datasketch`, `sentence-transformers`, `faiss-cpu`, `pdfplumber`, `python-docx`, `confusable-homoglyphs`). Install and import them directly.
7. **Strict Legal Boundaries:** Never decompile, scrape, automate queries against, or reverse-engineer Turnitin, GPTZero, Copyleaks, or any closed commercial detector.

---

## 3. Canonical Repository Layout

Maintain this exact directory structure throughout the project:

```text
originality-checker/
├── AGENTS.md                           # This rulebook (also symlink/copy to CLAUDE.md)
├── Originality_Checker_Repo_Based_Plan.md
├── THIRD_PARTY_LICENSES.md             # Attribution & license tracking for all 10 repos + libraries
├── research/                           # Cloned upstream repos (gitignored from our repo)
│   ├── Binoculars/
│   ├── fast-detect-gpt/
│   ├── detecting-fake-text/
│   ├── copydetect/
│   └── dolos/
├── rea/                                # REA evidence & rebuild specs (committed to git)
│   ├── binoculars/
│   │   ├── 01-target.md
│   │   ├── 02-stack.md
│   │   ├── 03-evidence.md
│   │   └── 04-spec.md
│   ├── fast-detect-gpt/
│   ├── gltr/
│   ├── copydetect/
│   └── dolos/
├── ingest/                             # Document parsing, Integrity Flags & sanitization
│   ├── flags.py                        # Red Flag detector (homoglyphs, invisible chars, hidden text)
│   ├── sanitizer.py                    # Normalizes homoglyphs & strips hidden text pre-scoring
│   ├── parser.py                       # PDF, DOCX, TXT extraction + header/footer/ref stripping
│   └── chunker.py                      # Sentence splitter + 250-word (50% overlap) windowing
├── detectors/                          # AI-writing detection modules
│   ├── binoculars.py                   # REA rebuild of Repo #1
│   ├── fastdetect.py                   # REA rebuild of Repo #2
│   ├── gltr_ranks.py                   # REA rebuild of Repo #3
│   ├── roberta_hc3.py                  # Iteration 2: REA rebuild of Repo #4
│   └── ensemble.py                     # Logistic-regression calibration & document AI % aggregation
├── similarity/                         # Plagiarism & paraphrase detection modules
│   ├── winnow.py                       # REA rebuild of Repo #6 (adapted to natural-language word tokens)
│   ├── lsh.py                          # Direct wrapper around datasketch MinHash LSH (Repo #8)
│   ├── semantic.py                     # Direct wrapper around sentence-transformers + FAISS (Repos #9 & #10)
│   └── aggregator.py                   # Merges exact + paraphrase spans into source-level Similarity %
├── api/                                # FastAPI backend, Celery/RQ workers & PostgreSQL models
├── web/                                # Next.js + Tailwind + shadcn/ui frontend
└── tests/                              # Differential tests & synthetic evaluation suites
    ├── diff_binoculars.py
    ├── diff_fastdetect.py
    ├── diff_gltr.py
    ├── diff_copydetect.py
    ├── test_integrity_flags.py
    └── fixtures/                       # Sample human, AI, and tampered DOCX/PDF files
```

---

## 4. Iteration 1 Execution Sequence (Strict Order)

Execute the work in these exact steps. Do not skip ahead.

| Step | Task | Target | Required Deliverable | Gate to Proceed |
|---|---|---|---|---|
| **0** | Workspace Setup | Repo scaffold & `rea-agents` skill | Folders created, `THIRD_PARTY_LICENSES.md` initialized, `rea-agents` active | User confirms workspace ready |
| **1** | REA Target #1 | `ahans30/Binoculars` | `rea/binoculars/01..04.md` -> `detectors/binoculars.py` -> `tests/diff_binoculars.py` | User approves `04-spec.md`; 50-sample diff test passes (`±0.001`) |
| **2** | REA Target #2 | `baoguangsheng/fast-detect-gpt` | `rea/fast-detect-gpt/01..04.md` -> `detectors/fastdetect.py` -> `tests/diff_fastdetect.py` | User approves `04-spec.md`; 50-sample diff test passes |
| **3** | REA Target #3 | `HendrikStrobelt/detecting-fake-text` (GLTR) | `rea/gltr/01..04.md` -> `detectors/gltr_ranks.py` -> `tests/diff_gltr.py` | User approves `04-spec.md`; 20-sample token-bucket diff test passes |
| **4** | REA Target #4 | `blingenf/copydetect` (word-token winnowing) | `rea/copydetect/01..04.md` -> `similarity/winnow.py` -> `tests/diff_copydetect.py` | User approves `04-spec.md`; identical fingerprint diff test passes |
| **5** | REA Target #5 | `dodona-edu/dolos` (UX & API contract) | `rea/dolos/01..04.md` -> JSON schema & report layout spec | User approves `04-spec.md` |
| **6** | Ingestion & Red Flags | `ingest/flags.py`, `sanitizer.py`, `parser.py`, `chunker.py` | Raw DOCX/PDF inspection + sanitization + `tests/test_integrity_flags.py` | ≥99% recall on tampered fixtures; ≤1% FP on styled cover pages/tables |
| **7** | Similarity & AI Wiring | `similarity/lsh.py`, `semantic.py`, `aggregator.py`, `detectors/ensemble.py` | End-to-end Python scoring pipeline + 2-signal calibration | Pipeline runs cleanly on a 2,000-word essay in ≤60s |
| **8** | Backend & Frontend MVP | `api/` (FastAPI + Redis + Postgres) & `web/` (Next.js) | Login, Dashboard, Upload, Report (Overview, Flags, AI, Similarity tabs) | Full upload-to-report flow verified locally |

---

## 5. Mandatory REA Stage Templates

Whenever running REA Stages 1–4 on a repository, create the four Markdown files in `rea/<repo>/` using these exact structures:

### `01-target.md`
* **Upstream Repository:** URL, commit hash checked out in `research/<repo>`, and license.
* **Exact Feature Scope:** Specific function(s), score, or data structure being extracted.
* **Out of Scope:** Training scripts, CLI wrappers, web servers, or UI assets we are ignoring.
* **Stage 5 Pass Condition:** Exact numeric tolerance or structural equality rule on `N` test samples.

### `02-stack.md`
* **Runtime & Dependencies:** Python/Node version, key packages, model weights downloaded.
* **Entry Points:** Exact files and functions executed to reproduce the upstream feature locally.
* **Hardware / VRAM Notes:** Observed memory footprint and quantization/batching notes.

### `03-evidence.md`
* **Execution Trace:** Step-by-step walkthrough of how inputs flow through the upstream code.
* **Mathematical & Algorithmic Details:** Exact formulas, tokenizer rules, window sizes, epsilon values, and thresholds—**every single claim must cite `file:line`**.
* **Edge Cases Observed:** Empty inputs, short texts, truncation limits, special tokens, numerical clamping.

### `04-spec.md`
* **Target Module Path:** e.g., `detectors/binoculars.py`.
* **Public Interface:** Function/class signatures, input types, output schema, and configuration parameters (e.g., model IDs, 4-bit/8-bit quantization flags).
* **Step-by-Step Rebuild Logic:** Clean pseudocode/specification without copying upstream variable names or boilerplate verbatim.
* **Confirmed vs. Unknowns:** Explicit list of anything not verified in upstream code and how our module handles it safely.

---

## 6. Architecture & Domain Rules (Do Not Violate)

### A. Integrity Flags / Red Flag Checker (`ingest/flags.py` & `ingest/sanitizer.py`)
* **Order of Operations:** Always inspect the raw uploaded file (`.docx` or `.pdf`) **before** extracting plain text. Plain-text conversion destroys color, font-size, and bounding-box metadata.
* **Three Required Flag Categories:**
  1. `replaced_character`: Words mixing Latin characters with visual lookalikes from other scripts (Cyrillic, Greek, Armenian, etc.) verified via Unicode script names and confusable mappings.
  2. `hidden_unicode`: Zero-width spaces, joiners, soft hyphens, BOMs, and bidirectional override characters.
  3. `hidden_text`: Pure/near-white font color, microscopic font size (`< 2pt`), Word's `hidden` font attribute, or PDF characters placed outside visible page boundaries.
* **False-Positive Guardrails:**
  * Do **not** flag white text placed over a dark PDF rectangle/banner or inside a shaded DOCX table cell.
  * Do **not** flag legitimate non-Latin paragraphs—only flag **mixed-script** words.
  * Group repetitive alerts per paragraph/page so teachers see clean summaries rather than hundreds of noisy rows.
* **Sanitization Rule:** Persist raw flags with character/page coordinates to PostgreSQL, then **strip hidden/invisible characters and map homoglyphs back to standard Latin** before passing text to AI detection or Similarity scoring.

### B. AI Detection (`detectors/`)
* **Length Guardrail:** If sanitized word count is `< 150` words, skip AI scoring and return status `"Too short to estimate"`.
* **Language Guardrail:** Detect non-English submissions and attach a visible confidence warning.
* **Resource Efficiency:** Support configurable model pairs and 4-bit/8-bit quantization in `detectors/binoculars.py` and `detectors/fastdetect.py` so workers can run on a single 24 GB GPU or serverless GPU without OOM crashes.
* **Low False-Positive Calibration:** Tune ensemble thresholds to keep human-essay false positives at **≤ 1–2%**.

### C. Similarity Detection (`similarity/`)
* **Tokenizer Adaptation:** When rebuilding `copydetect`'s Winnowing algorithm in `similarity/winnow.py`, strip Pygments source-code lexing and replace it with normalized natural-language word tokens (`5-grams`, window size `4`) while preserving exact character start/end offsets for UI highlighting.
* **Two-Stage Retrieval:** Use `datasketch` MinHash LSH (`similarity/lsh.py`) to narrow archive candidates before running exact Winnowing; run `sentence-transformers` + FAISS (`similarity/semantic.py`) on 20–200 word chunks (flagging cosine similarity `≥ 0.75`) to catch paraphrasing.

### D. UI & Reporting Ethics (`web/`)
* Never display definitive verdicts like `"100% AI"` or `"Plagiarized"`. Always display `"Likely AI-generated (Estimate)"` alongside evidence panels and a clear disclaimer.
* The Report Overview must surface three clear indicators: **AI Score (%)**, **Similarity Score (%)**, and the **Red Flags Badge** (linking to the dedicated **Flags** tab).

---

## 7. Ready-to-Use Kickoff Prompts

Copy and paste these prompts one at a time into your coding agent:

### Prompt 1 — Bootstrap & First REA Target (Stages 1–4)
> Read `AGENTS.md` and `Originality_Checker_Repo_Based_Plan.md`. Execute **Step 0 (Workspace Setup)** and **Step 1 (REA Stages 1–4 only)** for Repo #1 (`ahans30/Binoculars`). Clone it into `research/Binoculars`, verify its license in `THIRD_PARTY_LICENSES.md`, run its inference locally to trace the scoring logic, and write `rea/binoculars/01-target.md` through `rea/binoculars/04-spec.md` with exact `file:line` citations. **Stop after `04-spec.md` and wait for my approval before writing `detectors/binoculars.py`.**

### Prompt 2 — Rebuild & Differential Test (Stage 5)
> My review of `rea/binoculars/04-spec.md` is complete. Execute **Stage 5** for Binoculars: implement `detectors/binoculars.py` cleanly from the spec, write `tests/diff_binoculars.py` comparing `research/Binoculars` vs. `detectors/binoculars.py` across 50 diverse text samples, and run the test until all outputs match within `±0.001`. Report the test results and stop before starting Repo #2.

### Prompt 3 — Repeat for Repos #2, #3, #4, and #5
> Proceed to the next repository in Section 4 (`Fast-DetectGPT` -> `GLTR` -> `copydetect` -> `Dolos`). Follow the exact same two-phase gate: complete REA Stages 1–4 with `file:line` citations first and **stop at `04-spec.md` for my review** before implementing the module and Stage 5 differential test.

### Prompt 4 — Build the Red Flag Checker & Ingestion Pipeline
> All Iteration 1 REA modules have passed Stage 5. Now execute **Step 6**: implement `ingest/flags.py`, `ingest/sanitizer.py`, `ingest/parser.py`, and `ingest/chunker.py` following Section 6A of `AGENTS.md`. Create synthetic DOCX and PDF fixtures in `tests/fixtures/` (including Cyrillic homoglyphs, zero-width spaces, hidden white text, and benign dark-banner cover pages) and verify that `tests/test_integrity_flags.py` passes with ≥99% tamper recall and 0 false positives on styled cover pages.