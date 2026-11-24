# Next Steps Playbook (Prompts 6–12 & Iteration 1 Completion)

> **Purpose:** Use this file right after completing the first 5 kickoff prompts from `AGENTS.md`. Place it in the root of `originality-checker/` alongside `Originality_Checker_Repo_Based_Plan.md` and `AGENTS.md`, then feed **Prompts 6 through 12** to your coding agent one at a time.

---

## 0. Quick Checkpoint Before Prompt 6

Before moving forward, confirm that your workspace already has these foundations passing:

- [ ] Repository folder structure (`research/`, `rea/`, `ingest/`, `detectors/`, `similarity/`, `api/`, `web/`, `tests/`) is initialized.
- [ ] `THIRD_PARTY_LICENSES.md` is created and updated for every cloned repository.
- [ ] All Iteration 1 REA targets (`Binoculars`, `Fast-DetectGPT`, `GLTR`, `copydetect`, and `Dolos` API/UX spec) have completed `01-target.md` through `04-spec.md`.
- [ ] Every rebuilt REA module (`detectors/binoculars.py`, `detectors/fastdetect.py`, `detectors/gltr_ranks.py`, `similarity/winnow.py`) passes its Stage 5 differential test in `tests/diff_*.py`.
- [ ] `ingest/flags.py`, `ingest/sanitizer.py`, `ingest/parser.py`, and `ingest/chunker.py` are implemented and passing `tests/test_integrity_flags.py`.

*(If any single REA module or `ingest/flags.py` is still pending, finish that module and verify its test passes before running Prompt 6.)*

---

## 1. What We Have to Build Next (Roadmap)

| Step | Focus Area | Target Files / Modules | Pass Gate |
|---|---|---|---|
| **Step 6** | Direct-install similarity engines & score aggregator | `similarity/lsh.py`, `similarity/semantic.py`, `similarity/aggregator.py`, `tests/test_similarity_pipeline.py` | Finds exact copies, near-duplicates, and paraphrases ($\ge 0.75$ cosine similarity) with accurate source-level % |
| **Step 7** | Calibration dataset & 2-signal AI ensemble | `detectors/ensemble.py`, `scripts/calibrate.py`, `tests/test_calibration.py` | Calibrated threshold hits $\le 1\text{--}2\%$ human false-positive rate; enforces $< 150$-word skip & non-English warning |
| **Step 8** | End-to-end Python pipeline orchestrator | `pipeline/runner.py`, `pipeline/schemas.py`, `tests/test_e2e_pipeline.py` | Runs Flags $\rightarrow$ Sanitize $\rightarrow$ AI + Similarity in strict order; outputs unified report JSON in $\le 60\text{ s}$ for 2,000 words |
| **Step 9** | Async backend API, queue & database | `api/main.py`, `api/models.py`, `api/worker.py`, `api/routes/*`, `docker-compose.yml` | Upload PDF/DOCX/TXT via API, process asynchronously via Redis + Celery/RQ, persist results & flags in PostgreSQL |
| **Step 10** | Next.js MVP frontend (Dolos + GLTR + Flags UI) | `web/app/*`, `web/components/report/*` | Teacher can log in, upload a file, inspect Red Flags, view AI highlights + GLTR word colors, and open side-by-side similarity diffs |
| **Step 11** | Hardening, PDF export & quality-gate audit | `api/export.py`, `THIRD_PARTY_LICENSES.md`, `tests/test_quality_gates.py` | All Section 9 quality targets verified, PDF report exports cleanly, auth/privacy/deletion controls verified |
| **Step 12** | Iteration 2 expansion (Post-MVP) | `detectors/roberta_hc3.py`, `similarity/web_search.py`, `web/components/clusters/*` | 3-signal fusion active, optional web search catches copied web text, Dolos submission clusters render |

---

## 2. Detailed Breakdown of Each Remaining Step

### Step 6 — Direct-Install Similarity & Aggregator
* **Do not run REA here:** `datasketch`, `sentence-transformers`, and `faiss-cpu` are clean MIT/Apache libraries—install and wrap them directly.
* **Candidate filtering (`similarity/lsh.py`):** Build a MinHash LSH index over archived submissions so new uploads only run expensive Winnowing comparisons against likely overlapping documents.
* **Semantic paraphrase detection (`similarity/semantic.py`):** Embed sanitized 20–200 word chunks with a multilingual MiniLM model, index them in FAISS, and classify matches using severity bands ($\ge 0.59$ low flag, $\ge 0.75$ medium paraphrase match, $\ge 0.90$ high match).
* **Unified Similarity % (`similarity/aggregator.py`):** Merge overlapping exact-copy spans (from `similarity/winnow.py`) and paraphrase spans (from `similarity/semantic.py`) without double-counting words, then compute overall Similarity % and per-source breakdown matching the Dolos fragment schema.

### Step 7 — AI Ensemble Calibration & Guardrails
* **Dataset assembly:** Prepare a held-out calibration split using human student essays (ideally pre-2022), fresh AI outputs from current models, and lightly edited AI text.
* **2-signal fusion (`detectors/ensemble.py`):** Fit a lightweight logistic-regression combiner over per-window `Binoculars` and `Fast-DetectGPT` scores, choosing the operating threshold explicitly for a low false-positive rate ($\le 1\text{--}2\%$ on human writing).
* **Window-to-document rollup:** Calculate **Document AI %** as the proportion of words falling inside windows whose fused probability meets or exceeds the threshold, while keeping sentence-level flags and GLTR word-rank buckets for the detail view.
* **Product guardrails:** Skip AI scoring with `"Too short to estimate"` when sanitized text has $< 150$ words; attach a non-English confidence warning when language detection flags non-English text.

### Step 8 — Pipeline Orchestrator (`pipeline/runner.py`)
* Enforce the exact dataflow order so tampering can never distort scores:
  1. **Raw File Inspection:** Run `ingest/flags.py` directly on the uploaded PDF/DOCX bytes to log white text, microscopic text ($< 2\text{ pt}$), hidden attributes, off-page PDF glyphs, invisible Unicode, and mixed-script homoglyphs.
  2. **Sanitization:** Pass raw text through `ingest/sanitizer.py` to remove hidden/invisible characters and normalize homoglyphs back to standard Latin.
  3. **Parsing & Windowing:** Clean headers/footers/optional references (`ingest/parser.py`) and produce sentences + 250-word windows with 50% overlap (`ingest/chunker.py`).
  4. **Parallel Analysis:** Run the AI detection ensemble + GLTR ranks and the Similarity suite (LSH $\rightarrow$ Winnowing + FAISS semantic search) against the sanitized text.
  5. **Unified Output:** Assemble one validated JSON report payload containing metadata, Integrity Flags with coordinates, AI %, Similarity %, and linked source fragments.

### Step 9 — Async Backend, Database & GPU Worker Separation
* **API (`api/`):** FastAPI service exposing authentication, class/assignment management, document upload (streaming raw files to S3-compatible object storage), job status polling, and report retrieval endpoints.
* **Database (`PostgreSQL`):** Tables for `users`, `assignments`, `submissions`, `fingerprints`, `integrity_flags` (structured JSONB with page/paragraph/character offsets), and `reports`.
* **Async Queue (`Redis` + `Celery` or `RQ`):** Separate lightweight CPU tasks (parsing, Integrity Flags, Winnowing, LSH) from GPU-heavy tasks (`Binoculars`, `Fast-DetectGPT`, `GLTR`). Design the GPU worker so it can run either on a 24–48 GB cloud GPU or a scale-to-zero serverless GPU (with 4-bit/8-bit quantization toggle).

### Step 10 — Next.js Report Website (`web/`)
Build the full teacher flow using Next.js, Tailwind CSS, and shadcn/ui:
* **Login & Access Isolation:** Teachers see only their own classes and submissions.
* **Dashboard:** Table showing submission name, date, word count, **AI %**, **Similarity %**, **Red Flags count**, and live job status (`queued` / `processing` / `done` / `failed`).
* **Upload Screen:** Drag-and-drop PDF/DOCX/TXT or paste text, assign to a class/assignment, and toggle reference-list exclusion.
* **Report Overview:** Large AI % and Similarity % cards, a highlighted **Red Flags badge** when count $> 0$, qualitative label (*Likely human* / *Mixed* / *Likely AI*), and an unavoidable `"Estimate only, not proof"` disclaimer.
* **Report — Flags Tab:** Summary cards grouped by **Hidden Text**, **Replaced Characters**, and **Invisible Characters**; clicking any alert scrolls to the passage and highlights the offending text in a red box with a plain-English explanation.
* **Report — AI Tab:** Highlighted AI-likely sentences; clicking a sentence opens the evidence drawer showing detector probabilities and GLTR word-level color ranks.
* **Report — Similarity Tab:** Color-coded passages mapped to a ranked source list, plus a **Dolos-style side-by-side comparison view** with synchronized fragment highlights.

### Step 11 — Hardening, PDF Export & Launch Audit
* **PDF Export:** Generate a downloadable PDF report summarizing scores, disclaimers, Integrity Flags, and matched sources.
* **Privacy & Security:** Enforce per-teacher authorization on every route, file-size and upload rate limits, encrypted file storage, retention timers, and one-click submission deletion.
* **License Audit:** Verify `THIRD_PARTY_LICENSES.md` contains copyright notices and license text for all reused repos and packages, and confirm HC3 data (CC-BY-SA) is kept strictly out of proprietary redistribution.
* **Quality Verification:** Run automated benchmarks checking every metric in Section 9 of `Originality_Checker_Repo_Based_Plan.md`.

### Step 12 — Iteration 2 Expansion (Only After MVP Works End-to-End)
1. Run REA Stages 1–5 on Repo #4 (`HC3` RoBERTa detector) and upgrade `detectors/ensemble.py` to 3-signal fusion; add Repo #5 (`GPT-2 output detector`) strictly as a regression baseline harness.
2. Add optional **Web Similarity Check** (extract 10–20 distinctive sentences $\rightarrow$ paid search API with strict per-document query cap $\rightarrow$ page fetch $\rightarrow$ Winnowing compare).
3. Add **Dolos-style Assignment Clusters** view to detect groups of students sharing text across an entire assignment.
4. Run a 2-week pilot with 3–5 teachers to gather real-world feedback and review false positives.

---

## 3. Ready-to-Paste Agent Prompts (Prompts 6–12)

Feed these prompts to your coding agent **one at a time**. Wait for every test gate to pass before sending the next prompt.

### Prompt 6 — Direct-Install Similarity Engines & Aggregator
> Read `AGENTS.md` and `NEXT_STEPS_PLAYBOOK.md`. Execute **Step 6**: install `datasketch`, `sentence-transformers`, and `faiss-cpu` directly (do not run REA on these libraries). Implement `similarity/lsh.py` (MinHash LSH candidate search), `similarity/semantic.py` (20–200 word chunk embeddings + FAISS search with severity bands at $\ge 0.59$, $\ge 0.75$, and $\ge 0.90$), and `similarity/aggregator.py` (merges `similarity/winnow.py` exact spans and `similarity/semantic.py` paraphrase spans without double-counting words to output total Similarity % and per-source fragments matching our Dolos spec). Write and run `tests/test_similarity_pipeline.py` covering exact copies, paraphrased paragraphs, and unrelated essays. Stop and report results.

### Prompt 7 — AI Ensemble Calibration & Guardrails
> Read `NEXT_STEPS_PLAYBOOK.md` Step 7. Implement `detectors/ensemble.py` and `scripts/calibrate.py` to fuse per-window `Binoculars` and `Fast-DetectGPT` scores using logistic regression calibrated for a $\le 1\text{--}2\%$ false-positive rate on human essays, plus GLTR token-rank attachment for highlighted windows. Enforce the $< 150$-word `"Too short to estimate"` guardrail and non-English confidence warning. Add `tests/test_calibration.py` verifying threshold behavior, document AI % aggregation, and both guardrails. Stop and report calibration metrics.

### Prompt 8 — End-to-End Pipeline Orchestrator
> Read `NEXT_STEPS_PLAYBOOK.md` Step 8. Implement `pipeline/schemas.py` and `pipeline/runner.py` to execute the full analysis flow in strict order: raw file inspection (`ingest/flags.py`) $\rightarrow$ persist raw flags $\rightarrow$ text sanitization (`ingest/sanitizer.py`) $\rightarrow$ parsing & windowing (`ingest/parser.py`, `ingest/chunker.py`) $\rightarrow$ AI detection + Similarity detection $\rightarrow$ unified report JSON. Write `tests/test_e2e_pipeline.py` testing a clean human essay, an AI essay, a plagiarized essay, and a tampered DOCX/PDF containing homoglyphs + hidden white text (proving tampering raises Red Flags **and** still yields accurate AI/Similarity scores after sanitization). Stop and verify all tests pass.

### Prompt 9 — Async FastAPI Backend, PostgreSQL & Worker Queue
> Read `NEXT_STEPS_PLAYBOOK.md` Step 9. Build the backend inside `api/`: FastAPI REST endpoints (auth, assignments, upload, status polling, report retrieval), PostgreSQL models/migrations (users, assignments, submissions, fingerprints, structured integrity flags, reports), S3-compatible file storage client, and Celery/RQ + Redis worker queues separating CPU ingestion/similarity tasks from GPU AI-detection tasks (with a configurable 4-bit/8-bit quantization flag). Provide `docker-compose.yml` for local Postgres + Redis + MinIO and write integration tests proving an uploaded file flows asynchronously from `queued` to `done`. Stop and verify locally.

### Prompt 10 — Next.js MVP Frontend (Dolos + GLTR + Flags UI)
> Read `NEXT_STEPS_PLAYBOOK.md` Step 10 and `rea/dolos/04-spec.md`. Build the Next.js + Tailwind + shadcn/ui frontend inside `web/` connected to our FastAPI backend: Login, Teacher Dashboard (with AI %, Similarity %, Red Flags count, and live job status), Drag-and-Drop Upload screen, and the 4-part Report screen (**Overview** with Red Flags badge and `"Estimate only, not proof"` disclaimer, **Flags tab** with grouped cards and red-boxed character highlights, **AI tab** with sentence highlights and GLTR word-color evidence panel, and **Similarity tab** with color-coded sources and Dolos-style side-by-side comparison). Verify the complete upload-to-report user journey locally.

### Prompt 11 — Hardening, PDF Export & Quality-Gate Verification
> Read `NEXT_STEPS_PLAYBOOK.md` Step 11 and Section 9 of `Originality_Checker_Repo_Based_Plan.md`. Add downloadable PDF report export (including scores, disclaimers, Integrity Flags summary, and source breakdown), enforce per-teacher data isolation, upload rate limits, retention/delete endpoints, and update `THIRD_PARTY_LICENSES.md` with full notices for all reused repos and packages. Run `tests/test_quality_gates.py` and print a pass/fail scorecard against all Section 9 targets (human FPR $\le 1\text{--}2\%$, exact-copy recall $\ge 95\%$, paraphrase recall $\ge 70\%$, tamper recall $\ge 99\%$, benign cover-page FP $\le 1\%$, 2,000-word runtime $\le 60\text{ s}$).

### Prompt 12 — Iteration 2 Expansion (Run After Iteration 1 MVP Sign-Off)
> Iteration 1 MVP is signed off. Execute **Step 12** in three gated sub-tasks, stopping for review between each:
> 1. Run REA Stages 1–5 on `Hello-SimpleAI/chatgpt-comparison-detection` (`detectors/roberta_hc3.py`) and upgrade `detectors/ensemble.py` to 3-signal fusion.
> 2. Implement the optional paid web-search similarity module (`similarity/web_search.py`) with a strict 10–20 query cap per document and verify it detects copied Wikipedia paragraphs.
> 3. Implement the Dolos-style Assignment Clusters view (`web/components/clusters/*`) showing groups of submissions sharing overlapping passages.

---

## 4. Iteration 1 "Done" Checklist

You are ready to launch a teacher pilot when every box below is checked:

- [ ] **Tamper-Proof Ingestion:** Homoglyphs, zero-width characters, and hidden white/tiny text trigger Red Flags ($\ge 99\%$ recall) without breaking downstream AI or Similarity scores, and benign dark-banner cover pages trigger $\le 1\%$ false flags.
- [ ] **Calibrated AI Estimates:** Human essays have $\le 1\text{--}2\%$ false positives, unedited AI essays hit $\ge 85\%$ detection, texts under $150$ words return `"Too short to estimate"`, and every score displays `"Estimate only, not proof"`.
- [ ] **Exact + Paraphrase Similarity:** Exact-copy recall $\ge 95\%$, paraphrase recall $\ge 70\%$, and side-by-side Dolos-style highlights align accurately to source text.
- [ ] **End-to-End Speed & Cost Control:** A 2,000-word essay finishes in $\le 60\text{ seconds}$ (with Integrity Flags in $< 1\text{ second}$) and GPU inference supports quantization / scale-to-zero workers.
- [ ] **Legal & Privacy Clean:** `THIRD_PARTY_LICENSES.md` is complete, no closed commercial detector was scraped or reverse-engineered, and teachers can delete student submissions on demand.