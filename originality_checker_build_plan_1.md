# Originality Checker: Build Plan (Reusing Open-Source Repos)

> **Approach:** don't start from scratch. Use the **REA ("Reverse Engineer Anything") method** in **Iteration 1** to extract and rebuild the core detection algorithms from open-source repositories, pair them with standard Python libraries and a deterministic Red Flag checker, and assemble them into one web product: a website with an AI-writing score, a Turnitin-style similarity report, and Turnitin-style **Integrity Flags (Red Flags)** to catch document tampering.

## 0. Ground rules (read first)

| Rule | Why | 
| ----- | ----- | 
| "Reverse engineering" here means the **REA method** applied to open-source repos: understand how each feature works, write an evidence-backed spec, rebuild it in our own modules, and prove it behaves the same | Legal and fast. We stand on proven research code, and REA gives every target repo the same repeatable process. | 
| REA itself warns against copying exact code or assets: **rebuild the behaviour, don't lift the code**. Where we do reuse code, the repo's license allows it and we keep its notices | Keeps the project clean even when a repo's license is unclear. | 
| **Never** reverse-engineer Turnitin, GPTZero, Copyleaks or any other closed product (scraping, decompiling, copying their outputs) | It breaks their terms of service and creates legal risk. | 
| Respect each repo's **license**: keep copyright notices and add a `THIRD_PARTY_LICENSES.md` | MIT, BSD and Apache code can be used commercially if attribution is kept. CC-BY-SA data needs attribution and share-alike. | 
| **No detector is 100% accurate**, Turnitin included | The UI must show an *estimate with evidence*, never a verdict. | 

**Platform note:** this approach needs Python, AI models (ideally on a GPU) and internet access. It **cannot run inside a Langdock App**, which allows no Python, no model hosting and no outside network. It must be a **separately hosted website**. The empty Langdock draft "Originality Checker" can be deleted or kept for a later lightweight version.

## 1. Product in one line

Upload or paste a document and get three results:

1. **AI score:** "X% of this text is likely AI-generated", with the AI-likely passages highlighted.

2. **Similarity score:** "Y% matches other sources", with each matching passage linked to its source: your own submission archive and, optionally, the web.

3. **Integrity Flags (Red Flags):** alerts for deliberate document manipulation (hidden text, replaced lookalike characters, and invisible Unicode characters) with exact locations pinpointed for review.

## 2. The 10 repos and how we use each (REA Rebuild vs. Direct Library)

To keep **Iteration 1** fast and focused, we only run the full 5-stage REA reverse-engineering process on repositories whose core algorithms must be extracted from research scripts or adapted (such as converting code fingerprinting into natural-language word fingerprinting). Clean, installable MIT/Apache libraries are imported directly.

### A. AI-writing detection (5 repos)

| \# | Repo | Iteration | Strategy | What we extract & how we reuse it | License | 
| ----- | ----- | ----- | ----- | ----- | ----- | 
| 1 | [**ahans30/Binoculars**](https://github.com/ahans30/Binoculars) | **Iteration 1** | **REA Rebuild** | Zero-shot score from two language models (observer and performer). Rebuild the score function into `detectors/binoculars.py` and keep their global threshold as the starting point | BSD-3-Clause | 
| 2 | [**baoguangsheng/fast-detect-gpt**](https://github.com/baoguangsheng/fast-detect-gpt) | **Iteration 1** | **REA Rebuild** | Conditional probability curvature score and score-to-probability mapping (`scripts/local_infer.py`, `scripts/fast_detect_gpt.py`). Rebuild into `detectors/fastdetect.py` | Check the LICENSE file before use | 
| 3 | [**HendrikStrobelt/detecting-fake-text (GLTR)**](https://github.com/HendrikStrobelt/detecting-fake-text) | **Iteration 1** | **REA Rebuild** | Per-token rank colouring (top-10 / top-100 / top-1000 / rest) and visual forensic UI. Rebuild into `detectors/gltr_ranks.py` and the report's word-level "why" panel | Apache-2.0 | 
| 4 | [**Hello-SimpleAI/chatgpt-comparison-detection (HC3)**](https://github.com/Hello-SimpleAI/chatgpt-comparison-detection) | **Iteration 2** | **REA Rebuild + Data** | The HC3 human-vs-ChatGPT dataset and RoBERTa detector (`Hello-SimpleAI/chatgpt-detector-roberta`) as a third classifier signal plus calibration/test data | Data CC-BY-SA; model is roberta-base fine-tuned | 
| 5 | [**openai/gpt-2-output-dataset**](https://github.com/openai/gpt-2-output-dataset) (`detector/`) | **Iteration 2** | **Reference Only** | Baseline test harness and negative/positive sample sets. Too old to trust as a standalone detector | Model card: MIT | 

### B. Similarity and plagiarism (5 repos)

| \# | Repo | Iteration | Strategy | What we extract & how we reuse it | License | 
| ----- | ----- | ----- | ----- | ----- | ----- | 
| 6 | [**blingenf/copydetect**](https://github.com/blingenf/copydetect) | **Iteration 1** | **REA Rebuild (Adapted)** | **Winnowing** fingerprinting (MOSS algorithm): k-gram hashing, window minimum selection, and slice mapping. Rebuild into `similarity/winnow.py` and swap its code tokenizer for a natural-language word tokenizer | MIT | 
| 7 | [**dodona-edu/dolos**](https://github.com/dodona-edu/dolos) | **Iteration 1 (UI) & 2 (Clusters)** | **REA UX & API Spec** | Report UX: pair list, side-by-side compare with linked highlights, submission clusters, and JSON API design for pairs and fragments | MIT | 
| 8 | [**ekzhu/datasketch**](https://github.com/ekzhu/datasketch) | **Iteration 1** | **Direct Install** | Install directly as a Python package for MinHash and LSH candidate search so new documents aren't compared against every past document | MIT | 
| 9 | [**huggingface/sentence-transformers**](https://github.com/huggingface/sentence-transformers) | **Iteration 1** | **Direct Install** | Install directly as a Python package for multilingual MiniLM sentence embeddings to catch paraphrased copying | Apache-2.0 | 
| 10 | [**XYR05/semantic-plagiarism-detector**](https://github.com/XYR05/semantic-plagiarism-detector) | **Iteration 1** | **Architecture Blueprint** | Reference pipeline for PDF/Word parsing, 20–200 word chunking, embeddings, FAISS vector search, and severity thresholds (≥0.59 flag, ≥0.75 medium, ≥0.90 high) | Check the LICENSE file (an MIT fork exists) | 

**Supporting libraries (not counted in the 10):** FAISS (vector index), pdfplumber and python-docx (file parsing and formatting inspection), Python's built-in Unicode database and a Unicode confusables/homoglyph package (for integrity flags), FastAPI, Celery or RQ with Redis, PostgreSQL, Next.js.

## 3. How the repos fit together

```
flowchart LR
    U[Teacher uploads PDF / DOCX / text] --> F[Integrity Flag Checker<br/>raw layout + Unicode scan]
    F -->|Raw manipulation flags| DB[(PostgreSQL)]
    F -->|Sanitized & normalized text| P[Parser + cleaner<br/>pattern from repo 10]
    P --> Q[(Job queue)]
    Q --> AI[AI detection service]
    Q --> SIM[Similarity service]

    subgraph AI[AI detection service]
      B[Binoculars score<br/>repo 1 - REA]
      F2[Fast-DetectGPT score<br/>repo 2 - REA]
      R[RoBERTa classifier<br/>repo 4 - Iter 2]
      G[Per-token ranks<br/>repo 3 - REA]
      B --> E[Calibrated ensemble]
      F2 --> E
      R --> E
    end

    subgraph SIM[Similarity service]
      W[Winnowing fingerprints<br/>repo 6 - REA]
      L[MinHash LSH candidates<br/>repo 8 - Direct]
      S[Sentence embeddings + FAISS<br/>repos 9 + 10]
      WEB[Optional web search<br/>paid search API - Iter 2]
    end

    E --> DB
    G --> DB
    W --> DB
    L --> W
    S --> DB
    WEB --> W
    DB --> UI[Report web page<br/>UX from repos 3 + 7 + Flags panel]

```

## 4. The REA method (configured for AI coding agents)

### 4.1 How to make an AI agent actually follow REA

Simply handing a Markdown plan to an AI coding agent (Claude Code, Codex, or Cursor) is not enough—without explicit setup and stage gates, agents tend to skip differential testing or copy source files directly. Before building any feature in **Iteration 1**, configure the workspace so the agent enforces **[morluto/rea](https://github.com/morluto/rea) ("Reverse Engineer Anything")**:

1. **Install the REA agent skill:** Install the `rea-agents` npm package and register its agent skill in the project workspace so the agent has access to REA's structured evidence-and-rebuild templates. (Because all target repos are open-source, binary decompilers like Ghidra or IDA are not needed—the agent applies REA directly to cloned source code in `research/`.)

2. **Create `CLAUDE.md` and `AGENTS.md` in the repo root:** Add non-negotiable house rules so every agent session loads them automatically:
   * *Process one target repository at a time—never jump ahead to full-app generation.*
   * *Rebuild behaviour cleanly in our own modules; never copy source files verbatim unless the license explicitly permits it.*
   * *Cite exact file paths and line numbers for every behavioural claim in `03-evidence.md`.*
   * *List unverified assumptions in `04-spec.md`.*
   * *Stop after Stage 4 (`04-spec.md`) for review before writing module code.*
   * *A rebuilt module is not complete until its Stage 5 differential test passes against the cloned original repository.*

### 4.2 The 5 REA stages, run once per target repo

| Stage | What the agent does | Output file | Gate |
|---|---|---|---|
| **1. Target** | Name the exact feature to extract (e.g. "Binoculars score for one text window") and define the numeric/behavioral pass condition | `rea/<repo>/01-target.md` | Must cite exact inputs & outputs |
| **2. Stack recon** | Identify language, frameworks, model weights, entry points, and dependencies | `rea/<repo>/02-stack.md` | Must verify local execution |
| **3. Inspect with evidence** | Run the original repo inside `research/<repo>`, trace core functions, and record inputs, outputs, thresholds, and edge cases, **citing file and line for every claim** | `rea/<repo>/03-evidence.md` | Every claim needs `file:line` |
| **4. Spec + unknowns** | Write a clean rebuild spec: function signature, maths, data formats, plus a list of things not confirmed | `rea/<repo>/04-spec.md` | **Mandatory pause for review** |
| **5. Rebuild + prove** | Rebuild the module in our codebase, then run a **differential test**: original vs. rebuild on the same 50 inputs, outputs must match within tolerance | `detectors/` or `similarity/` + `tests/diff_<repo>.py` | **Must pass before next repo** |

### 4.3 Iteration 1 REA target cards (execute in this exact order)

In **Iteration 1**, the agent executes the 5 REA stages on these 5 targets in sequence:

| Order | Repo | REA target (Stage 1) | Rebuilt module | Differential test (Stage 5) |
|---|---|---|---|---|
| **1** | **Binoculars** (Repo 1) | Observer/performer score and threshold for one text window | `detectors/binoculars.py` | Same score as the original on 50 texts (±0.001) |
| **2** | **Fast-DetectGPT** (Repo 2) | Analytic curvature score + probability mapping | `detectors/fastdetect.py` | Same criterion and probability on 50 texts |
| **3** | **GLTR** (Repo 3) | Per-token rank buckets (top-10 / top-100 / top-1000 / rest) | `detectors/gltr_ranks.py` + UI highlight spec | Same bucket for every token on 20 texts |
| **4** | **copydetect** (Repo 6) | Winnowing: k-gram hashes, window minima, slice mapping (adapted to word tokens) | `similarity/winnow.py` | Same fingerprints as the original when fed the same normalized token stream |
| **5** | **Dolos** (Repo 7) | Pair list, side-by-side comparison view, and fragment JSON API contract | `api/schemas/report.py` + `web/report/*` | Verified side-by-side fragment alignment on a 10-document test set |

### 4.4 Iteration 2 REA target cards (post-MVP expansion)

Once Iteration 1 works end-to-end, run REA on the remaining classifier repos:

| Order | Repo | REA target (Stage 1) | Rebuilt module | Differential test (Stage 5) |
|---|---|---|---|---|
| **6** | **HC3** (Repo 4) | RoBERTa detector inference + HC3 dataset loader | `detectors/roberta_hc3.py`, `data/hc3.py` | Same label/probability on 50 HC3 samples |
| **7** | **GPT-2 output detector** (Repo 5) | Baseline scoring harness for regression benchmarking | `tests/baselines/roberta_gpt2.py` | Same probability on 50 samples |

### 4.5 Optional "watch from outside" study of Turnitin-style products

REA also supports black-box study: observing what a feature **does** from the outside. We may study **publicly available** material only: documentation, published sample reports and help pages for Turnitin, GPTZero and Copyleaks, used to understand report layout, integrity flag wording, and presentation. **No** decompiling, scraping, account sharing or automated querying of those services.

## 5. Pipeline details

### 5.1 Ingestion (pattern from repo 10)

* Accept PDF, DOCX, TXT or pasted text, up to about 20,000 words.

* **Run the Integrity Flag Checker first** on the raw uploaded file (see section 5.2), before stripping styles or converting to plain text.

* Sanitize and normalize the extracted text (remove hidden text, strip invisible characters, map replaced lookalike characters back to standard letters), then strip headers, footers, page numbers and the reference list (optional toggle) and normalise whitespace.

* Split into **sentences** and into **windows** of about 250 words with 50% overlap.

### 5.2 Integrity Flags / Red Flag Checker (deterministic, CPU-only)

Turnitin-style red flags catch deliberate attempts to bypass AI and similarity detectors rather than judging writing style. Because this stage relies on deterministic rules and document metadata, it runs in under a second on a standard CPU and requires no ML models.

**How to implement it step by step:**

1. **Replaced Characters (Homoglyphs & Mixed Scripts):**

   * Scan every word in the document to identify which writing script each letter belongs to (Latin, Cyrillic, Greek, Armenian, etc.).

   * Flag any word that mixes scripts (for example, a Cyrillic letter disguised inside an otherwise English/Latin word) and verify whether the non-Latin letter is a known visual lookalike using standard Unicode confusable mappings.

   * Record the flag type, the offending word, the exact character position, and the script name.

2. **Invisible Unicode Characters:**

   * Scan the raw text stream for zero-width spaces, zero-width joiners, soft hyphens, byte-order marks, and bidirectional text override characters often inserted between letters to break word matching.

   * Record the character category and exact position in the document.

3. **Hidden Text (Format-Layer Inspection for DOCX and PDF):**

   * Inspect document formatting **before** extracting plain text, since plain-text extraction discards font colors, sizes, and coordinates.

   * **Color matching:** Flag text styled in pure white or near-white color (commonly used to hide extra characters between words to fuse them together or inflate word counts).

   * **Microscopic text:** Flag text shrunk below a readable threshold (for example, smaller than 2pt).

   * **Hidden attributes & off-page placement:** Flag text explicitly marked with the "hidden" font property in Word documents, or PDF characters positioned outside the visible page borders.

4. **False-Positive Guardrails:**

   * **Background awareness:** Avoid flagging white text sitting on top of a dark banner, colored cover-page header, or shaded table cell. Check whether a dark shape or shaded cell sits behind the text before raising a hidden-text flag.

   * **Multilingual fairness:** Never flag a word simply for being non-Latin; only flag **mixed-script** words where a foreign lookalike character is spliced into a Latin word.

   * **Severity grouping:** Summarize repetitive flags cleanly (e.g., "42 replaced characters across 14 paragraphs") instead of overwhelming teachers with dozens of separate alerts.

5. **Sanitize Before Scoring (Critical):**

   * Save every raw flag and its exact document coordinates to PostgreSQL for the UI report.

   * **Before passing text to the AI and Similarity services**, delete detected hidden/invisible text and replace homoglyphs with their standard Latin equivalents. This guarantees that tampering both triggers a red flag **and** fails to lower the AI or similarity score.

### 5.3 AI score (repos 1–5)

1. **Iteration 1:** Run **Binoculars** and **Fast-DetectGPT** on every sanitized window, combining their calibrated probabilities with GLTR word-level rank highlighting. **Iteration 2:** Add the fine-tuned **RoBERTa** classifier (repo 4).

2. **Calibrate:** train a small logistic-regression "fusion" model on held-out labelled data (HC3 plus our own human essays plus fresh AI samples from current models). It turns the detector scores into one probability per window.

3. **Document AI %** = share of words that sit in windows with probability ≥ the threshold. This is how "X% of the text" is reported in Turnitin-style tools.

4. **Highlighting:** flag sentences in high-probability windows, and show GLTR-style word colours in the detail panel (repo 3).

5. **Guardrails:**

   * Below 150 words: no score, with the message "Too short to estimate."

   * Non-English text: warn that accuracy is lower (Binoculars itself notes it works best in English).

   * Set the threshold for a **low false-positive rate**. Wrongly accusing a student is worse than missing one.

### 5.4 Similarity score (repos 6–10)

1. **Exact and near-exact copying (repo 6 - REA):** word 5-grams → hash → winnow with window 4 → store fingerprints with their positions.

2. **Candidate search (repo 8 - Direct library):** MinHash LSH finds archive documents that probably overlap. Winnowing then runs only on those candidates.

3. **Paraphrase (repos 9 + 10 - Direct library + blueprint):** embed 20–200 word chunks, search FAISS, and flag pairs at ≥0.75 cosine similarity (tunable).

4. **Optional web check (Iteration 2):** pick the 10–20 most distinctive sentences → query a paid web-search API → fetch the top pages → winnow-compare. This is the only way to approximate Turnitin's internet check, and it costs money per query.

5. **Similarity %** = share of the document's words covered by any match (exact or paraphrase), with a breakdown by source.

## 6. The website (screens)

UX inspired by Dolos (repo 7), GLTR (repo 3), and Turnitin's Insights/Flags panel.

| Screen | Contents | 
| ----- | ----- | 
| **Login** | Email login; each teacher sees only their own data | 
| **Dashboard** | Table of submissions: name, date, words, AI %, Similarity %, **Red Flags count**, status (queued / processing / done / failed) | 
| **Upload** | Drag-and-drop for PDF/DOCX/TXT or paste text; choose the class or assignment; tick "check the web" (optional in Iteration 2) | 
| **Report: Overview** | Two large scores (AI % and Similarity %), a **Red Flags badge** (highlighted in red when > 0), a label (Likely human / Mixed / Likely AI), and an "Estimate only, not proof" note | 
| **Report: Flags tab** | Summary cards for **Hidden Text**, **Replaced Characters**, and **Invisible Characters**; clicking any flag jumps directly to the passage and draws a red box around the suspicious characters with a plain-English explanation | 
| **Report: AI tab** | Full text with AI-likely sentences highlighted; click a sentence to see detector scores and GLTR word colours | 
| **Report: Similarity tab** | Text with colour-coded matches per source; a source list with percentages; **side-by-side compare** (Dolos style) | 
| **Assignment view** | Clusters of students sharing text (Dolos style - Iteration 2) | 
| **Export** | Download the report as PDF (including Integrity Flags summary) | 

## 7. Tech stack

| Layer | Choice | 
| ----- | ----- | 
| Frontend | Next.js + Tailwind + shadcn/ui | 
| API | FastAPI (Python) | 
| Jobs | Celery or RQ + Redis (detection takes seconds to minutes) | 
| Database | PostgreSQL (users, submissions, results, fingerprints, structured integrity flags) | 
| Vector search | FAISS | 
| Models | Hugging Face Transformers on a GPU server (or scale-to-zero serverless GPU in Iteration 1) | 
| Storage | S3-compatible storage for uploaded files | 
| Hosting | Frontend on Vercel or similar; API and GPU worker on a cloud GPU (one 24–48 GB card or serverless equivalent) | 

**Model size note:** the Binoculars and Fast-DetectGPT defaults use Falcon-7B and Falcon-7B-Instruct, two 7B models (about 28 GB in fp16). Options:

* **Full:** 1× A100 40/80 GB.

* **Budget (recommended for Iteration 1):** 8-bit or 4-bit loading, or smaller model pairs hosted on a scale-to-zero GPU worker so you only pay per document processed. Smaller pairs mean the thresholds **must be re-calibrated**.

## 8. Build phases (Iteration 1 vs. Iteration 2)

### Iteration 1: REA Core MVP (Weeks 1–7)

| Phase | Weeks | Output | Done when |
|---|---|---|---|
| **1.0 Agent & REA Bootstrap** | 0.5 | Repo scaffold (`research/`, `rea/`, `detectors/`, `similarity/`, `ingest/`, `api/`, `web/`), `rea-agents` skill installed, `CLAUDE.md` & `AGENTS.md` active | Agent successfully completes a dry-run Stage 1–4 spec generation with file-and-line citations |
| **1.1 REA Core Extraction** | 2.5 | Execute REA Stages 1–5 sequentially for **Binoculars**, **Fast-DetectGPT**, **GLTR**, and **copydetect** (`detectors/*.py`, `similarity/winnow.py`) | Every rebuilt module passes its Stage 5 differential test against the original repo |
| **1.2 Ingestion, Flags & Direct Libs** | 1 | `ingest/flags.py` (integrity flag checker & sanitizer), `ingest/parser.py`, `ingest/chunker.py`, plus `datasketch` LSH and `sentence-transformers` + FAISS wiring | Synthetic tampering tests (white text, homoglyphs, zero-width chars) and semantic chunk searches pass |
| **1.3 Calibration & Backend** | 1.5 | Initial 2-signal calibration (Binoculars + Fast-DetectGPT), FastAPI, job queue, PostgreSQL schema, results API | End-to-end job runs from file upload to stored flags, AI %, and similarity % |
| **1.4 MVP Website (Dolos-style)** | 1.5 | Dashboard, upload, Report tabs (Overview, Flags, AI with GLTR highlights, Similarity side-by-side compare) | A teacher can upload a document, inspect red flags, and view AI/similarity highlights |

### Iteration 2: Ensemble Expansion, Web Search & Hardening (Weeks 8–12)

| Phase | Weeks | Output | Done when |
|---|---|---|---|
| **2.1 Classifier & Fusion Upgrade** | 1.5 | REA extraction of HC3 RoBERTa (`detectors/roberta_hc3.py`), GPT-2 baseline harness, and 3-signal logistic-regression fusion calibration | Quality targets in section 9 are met across all test sets |
| **2.2 Web Check & Clusters** | 1.5 | Optional paid web-search API integration + Dolos-style assignment cluster view | Copied Wikipedia text is found and student submission clusters render |
| **2.3 Hardening & Pilot** | 2 | Auth, data retention/deletion, rate limits, PDF export, `THIRD_PARTY_LICENSES.md`, and 3–5 teacher pilot | Security/license checklist is clear and pilot false positives are reviewed |

## 9. Quality targets (measure, don't guess)

| Metric | Target | 
| ----- | ----- | 
| False positive rate (human essays flagged as AI) | **≤ 1–2%** at the chosen threshold | 
| AI detection rate on unedited AI text | ≥ 85% | 
| AI detection on paraphrased or edited AI text | Report it honestly; it will be lower | 
| Exact-copy recall (copied paragraphs found) | ≥ 95% | 
| Paraphrase recall | ≥ 70% | 
| Integrity Flag detection (homoglyphs, invisible chars, hidden white/tiny text) | **≥ 99%** recall on deliberate tampering | 
| Integrity Flag false positives on normal formatted docs (cover pages, tables) | **≤ 1%** | 
| Report time for a 2,000-word essay | ≤ 60 seconds (Integrity Flags < 1 second) | 

**Test data:** HC3 (repo 4), the GPT-2 output samples (repo 5), **your own pre-2022 student essays** (the best human baseline), fresh samples from today's AI models, and a small synthetic tampering suite (DOCX/PDF files with Cyrillic swaps, zero-width characters, hidden white text, and benign dark-banner cover pages).

## 10. Risks and mitigations

| Risk | Mitigation | 
| ----- | ----- | 
| Agent skips REA stages or copies code | Enforce `CLAUDE.md` / `AGENTS.md` rules, process one repo at a time, and block merges unless Stage 5 differential tests pass |
| False accusations | Low-FPR threshold, an "estimate" label, evidence panels, no automatic penalties | 
| False red flags on styled documents | Background-color/shading checks for white text on cover pages and tables; only flag mixed-script words rather than legitimate non-Latin text | 
| New AI models evade detection | Re-calibrate every quarter with fresh samples; the ensemble is not tied to one model | 
| Non-native writers flagged more often | Include non-native essays in the test set and check the FPR per group | 
| GPU cost | Batch jobs, quantized/budget model pair, and scale-to-zero serverless GPU | 
| Licenses | Track each repo's license; keep notices; HC3 data stays for calibration only (share-alike) | 
| Student privacy | Encrypt storage, set a retention period, add a delete button and get consent wording from the school | 
| Web search cost and limits | Make it optional per check; cap queries per document | 

## 11. Team and skills

* **ML engineer:** REA detector extraction, calibration and evaluation (Iterations 1 & 2)

* **Full-stack developer:** API, queue, ingestion/integrity flags, database and website (Iterations 1 & 2)

* **Teacher advisor:** test essays, thresholds and wording of results

## 12. Next 5 actions (Iteration 1 Kickoff)

1. Create the repo `originality-checker/` with folders `research/`, `rea/`, `detectors/`, `similarity/`, `ingest/`, `api/`, `web/`, and `tests/`.

2. Install the `rea-agents` skill in the workspace and write `CLAUDE.md` and `AGENTS.md` containing the Section 4.1 & 4.2 REA stage rules.

3. Hand this Markdown file to your coding agent with a strict first prompt: instruct it to **only execute Phase 1.0 and REA Stages 1–4 for Repo #1 (`ahans30/Binoculars`)**—writing `rea/binoculars/01-target.md` through `04-spec.md` with exact file-and-line citations—and to **stop for your review** before writing `detectors/binoculars.py` or running Stage 5.

4. Collect 200 human essays, 200 AI-written essays, and 15–20 tampered DOCX/PDF test files (homoglyphs, white text, invisible characters) for the Iteration 1 test and differential-testing suite.

5. Once `Binoculars`, `Fast-DetectGPT`, `GLTR`, and `copydetect` pass their Stage 5 differential tests, build `ingest/flags.py` (integrity flag checker + sanitizer) and wire up the Iteration 1 FastAPI + Next.js MVP.