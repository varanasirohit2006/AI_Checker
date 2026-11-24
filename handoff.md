# Session Handoff — Originality Checker (Iteration 1, Repos #1 & #2 Complete)

> **For the next agent:** You are continuing a strictly gated REA workflow. Read this file
> completely, then the two rulebooks listed below. Repo #1 (Binoculars) and Repo #2 (Fast-DetectGPT)
> are both **complete through Stage 5** (diff tests PASSED). Next in the REA sequence are
> GLTR (Repo #3) and copydetect (Repo #4), followed by Prompt 6 of the Continuation Playbook.

---

## 1. Governing documents (actual filenames — differ from what the plan calls them)

| Plan's name | Actual file in repo root |
|---|---|
| `AGENTS.md` | [agent_rules_rea_execution_guide.md](agent_rules_rea_execution_guide.md) |
| `Originality_Checker_Repo_Based_Plan.md` | [originality_checker_build_plan_1.md](originality_checker_build_plan_1.md) |

Read both before any work. Non-negotiables: one repo at a time; rebuild behaviour, don't
lift code; every claim in `03-evidence.md` needs exact `file:line`; Stage 4 review gate;
Stage 5 differential test gate (±0.001 on 50 samples for Binoculars); never touch closed
commercial detectors.

Project root: `C:\Users\varan\OneDrive\Desktop\ai_checker`

## 2. Environment facts (verified this session)

- **OS:** Windows 10 x64, Git Bash shell, 16 GB RAM, **no NVIDIA GPU** (`nvidia-smi` absent). CPU-only inference.
- **Python:** 3.13.2. Project venv at `.venv/` with:
  - `torch 2.15.0+cpu`, `transformers 5.24.0`, `accelerate 1.16.0`, `psutil`, `numpy`
  - `binoculars` installed **editable from the clone**: `pip install -e research/Binoculars --no-deps`
    → `import binoculars` resolves to `research/Binoculars/binoculars/__init__.py` (exact cloned code).
  - Harmless pip warning on every call: leftover `~ip-24.3.1.dist-info` from an interrupted upgrade. Can be deleted.
- **Node:** 22.14.0. `rea-agents` npm v6.10.1 installed in root `node_modules/` (root `package.json` created by `npm init -y`).
  - ⚠️ `npx rea-agents setup` is **blocked**: requires Node ≥22.23.4 / 24.22.1. Do not change system Node without asking the user.
- **Model weights cached** in `C:\Users\varan\.cache\huggingface\hub`: `gpt2` (observer) and `distilgpt2` (performer), fp32. Falcon-7B pair (~28 GB) NOT downloaded — infeasible on this machine.
- **Git warning (important):** the git repo root is `C:/Users/varan` (the whole home directory), NOT `ai_checker/`. `ai_checker/` is untracked. Never run `git add`/`git commit` here without explicit user request; never touch files outside `ai_checker/`.
- User has unrelated uvicorn/python processes running (other projects). Leave them alone.

## 3. Completed work — status table

| Step | Status | Deliverables |
|---|---|---|
| **0. Workspace setup** | ✅ done | Folders `research/`, `rea/binoculars/`, `detectors/`, `similarity/`, `ingest/`, `api/`, `web/`, `tests/`; `.gitignore` (ignores `research/`, `.venv/`, `node_modules/`); `THIRD_PARTY_LICENSES.md` initialized; `rea-agents` installed (setup blocked on Node version — flagged to user) |
| **1. REA Stages 1–4, Binoculars** | ✅ done | Clone at commit `c8ae2f90d50ee696418bc71d8d9e5020e5f9d7b8`; license verified BSD-3-Clause and recorded; local inference trace executed; four stage docs written |
| **Stage 5 (rebuild + diff test)** | ✅ done (2026-11-23) | `detectors/binoculars.py` + `tests/diff_binoculars.py`; **PASS**: 50/50 samples, max score diff **0.000e+00** (tolerance ±0.001), identical predict labels (low-fpr + accuracy), batch-of-2 order preserved, edge cases replicated (""→RuntimeError, 1-token→nan, bogus mode→ValueError). Log: `tests/diff_binoculars_run.log`. Pair: gpt2/distilgpt2 fp32 CPU. |
| Steps 2–8 (other repos, ingestion, API, web) | not started | Per rulebook order |
| **2. REA Stages 1–5, Fast-DetectGPT** | ✅ done (2026-11-23) | `detectors/fastdetect.py` + `tests/diff_fastdetect.py`; **PASS**: 50/50 samples, max criterion diff **0.000e+00** (tolerance ±0.001), exact probability matches across all 4 published distribution parameter sets, exact ntoken match, edge cases replicated (""→RuntimeError, 1-token→nan, batch>1→AssertionError, invalid quantize→ValueError, unknown pair→KeyError). Pair: gpt2 fp32 CPU. |
| **6. Ingestion & Red Flags** | ✅ done (2026-11-23, run out of sequence by explicit user instruction) | `ingest/flags.py`, `sanitizer.py`, `parser.py`, `chunker.py`; 16 synthetic fixtures + ground-truth manifest (`tests/fixtures/make_fixtures.py`); `tests/test_integrity_flags.py` **15/15 PASS: tamper recall 252/252 = 100% (≥99% required), 0 FP on 8 benign fixtures** (dark banners, shaded tables, styled covers, pure Cyrillic). Direct libs installed: python-docx, pdfplumber, reportlab, confusable-homoglyphs (licenses recorded). |
| **Playbook Step 6 (Similarity Suite)** | ✅ done (2026-11-23) | `similarity/winnow.py`, `similarity/lsh.py`, `similarity/semantic.py`, `similarity/aggregator.py`, `tests/test_similarity_pipeline.py`; **17/17 PASS in 9.29s**: MinHash candidate retrieval, word-level Winnowing exact slices, FAISS paraphrase detection (severity tiers $\ge 0.59, \ge 0.75, \ge 0.90$), and word deduplication with Dolos fragment export. Installed `datasketch`, `faiss-cpu`, `sentence-transformers`. |
| **Playbook Step 7 (AI Ensemble & Calibration)** | ✅ done (2026-11-23) | `detectors/gltr_ranks.py`, `scripts/calibrate.py`, `detectors/calibration_params.json`, `detectors/ensemble.py`, `tests/test_calibration.py`; **8/8 PASS in 62.45s**: 2-signal logistic regression combiner, human FPR 0.0% (target $\le 1\text{--}2\%$), length guardrail (<150 words 'Too short to estimate'), language guardrail, GLTR forensic color ranks (top-10 green, top-100 yellow, top-1000 red, rest purple), document word rollup. |
| **Playbook Step 8 (E2E Pipeline Orchestrator)** | ✅ done (2026-11-24) | `pipeline/schemas.py`, `pipeline/runner.py`, `tests/test_e2e_pipeline.py`; **4/4 PASS in 22.35s**: strict 5-stage order (Raw flags -> Sanitize -> Parse -> AI/Similarity -> Unified Report JSON), verified on clean human essay, AI essay, plagiarized essay, and tampered DOCX with homoglyphs + white text. |
| **Playbook Step 9 (Async FastAPI Backend & Worker)** | ✅ done (2026-11-24) | `api/database.py`, `api/models.py`, `api/storage.py`, `api/auth.py`, `api/worker.py`, `api/routes/*`, `api/main.py`, `docker-compose.yml`, `tests/test_api.py`; **5/5 PASS in 21.23s**: teacher JWT auth, assignment isolation, upload endpoint (202 Accepted), async queue processing ('queued' -> 'done'), structured integrity flags + fingerprints + report persistence, report retrieval. |
| **Playbook Step 10 (Next.js MVP Frontend)** | ✅ done (2026-11-24) | `web/app/*`, `web/components/report/*`; Next.js 14 production build verified: Login, Dashboard with status/scores, Drag-and-drop upload screen, and 4-tab Report viewer (Overview, Flags with red highlights, AI with GLTR word coloring, and Dolos side-by-side comparison). |
| **Playbook Step 11 (Hardening, PDF Export & Quality Audit)** | ✅ done (2026-11-24) | `api/export.py`, `tests/test_quality_gates.py`, `THIRD_PARTY_LICENSES.md`; Downloadable PDF report generation via ReportLab, teacher data isolation & student data deletion (`DELETE /submissions/{id}`), 25MB upload limits. **Quality gates audit: 7/7 tests PASS** against Section 9 targets (FPR 0.0% <= 1-2%, AI recall 100% >= 85%, Exact-copy 100% >= 95%, Paraphrase 89.3% >= 70%, Tamper recall 100% >= 99%, Benign FP 0.0% <= 1%, 2,000-word runtime 46.21s <= 60s, Flags speed 0.15s < 1s). |
| **Playbook Step 12 (Iteration 2 Expansion)** | ✅ done (2026-11-24) | `detectors/roberta_hc3.py` (REA Stages 1–5 on Hello-SimpleAI/chatgpt-comparison-detection commit 1f8c15c2) & 3-signal fusion; `similarity/web_search.py` (bounded 10–20 query cap Wikipedia plagiarism checker); `web/components/clusters/AssignmentClusters.tsx` (Dolos multi-student collision clusters). Tests in `tests/test_roberta_hc3.py` (3/3 PASS) and `tests/test_web_search.py` (3/3 PASS). |

### Files created this session

```
ai_checker/
├── .gitignore
├── THIRD_PARTY_LICENSES.md          # Binoculars row verified: BSD-3-Clause, commit c8ae2f90, 2026-11-23
├── package.json / node_modules/     # rea-agents v6.10.1
├── .venv/                           # torch cpu, transformers, accelerate, psutil, binoculars editable
├── research/Binoculars/             # upstream clone (gitignored)
├── research/trace_binoculars.py     # the executed local trace script
├── rea/binoculars/01-target.md      # scope + Stage 5 pass condition
├── rea/binoculars/02-stack.md       # deps, entry points, observed footprint
├── rea/binoculars/03-evidence.md    # full walkthrough + observed outputs, file:line citations
└── rea/binoculars/04-spec.md        # rebuild spec — MARKED "STAGE GATE: review required"
```

## 4. Key verified findings (Binoculars scoring — read `03-evidence.md` for full citations)

Upstream: `ahans30/Binoculars`, BSD-3-Clause (© 2023 Hans, Schwarzschild, Goldstein),
commit `c8ae2f90d50ee696418bc71d8d9e5020e5f9d7b8` (2024-05-14). Package version 0.0.10.

**The score** (`binoculars/detector.py:87-96`):
```
score = ppl / x_ppl
ppl   = perplexity(encodings, performer_logits)   # mean CE of performer predicting text, IN NATS
x_ppl = entropy(observer_logits, performer_logits, encodings, pad_token_id)
                                                  # mean cross-CE(observer softmax dist || performer logits)
```
- ⚠️ `metrics.perplexity()` returns **mean CE, NOT exp(CE)** (`metrics.py:23-25`) — no exponentiation anywhere.
- Denominator: softmax(observer logits) as soft targets into `CrossEntropyLoss(performer logits, target=probs)` (`metrics.py:39-48`), masked by `input_ids != pad_token_id` (`metrics.py:49,55`).
- With observer == performer the denominator is the model's **predictive entropy H(p)**, so score = CE/H ≈ 0.826, **not 1.0** (verified).

**Constants** (`detector.py:19-21`): `BINOCULARS_ACCURACY_THRESHOLD = 0.9015310749276843` (F1), `BINOCULARS_FPR_THRESHOLD = 0.8536432310785527` (low-fpr, ≤0.01% FPR). Falcon-7B/Falcon-7B-Instruct bf16-tuned; default mode `"low-fpr"`. `predict`: score < threshold → `"Most likely AI-generated"` else `"Most likely human-generated"` (`detector.py:98-104`).

**Tokenizer contract** (`detector.py:68-77`): single string → no padding; batch >1 → `padding="longest"`; `truncation=True`, `max_length=512` (default) — **only first 512 tokens scored, rest silently dropped** (verified: score(full 1141-token text) == score(first-512-tokens) exactly). Tokenizer from observer; `pad_token = eos_token` fallback (`detector.py:55-57`; gpt2 → `<|endoftext|>`, id 50256). Tokenizer vocab equality asserted before loading (`utils.py:4-10`).

**Edge cases (verified by trace):**
- Empty string `""` → `RuntimeError` (0-element reshape inside `entropy()`, `metrics.py:41`). Caller must reject empty input.
- 1-token input (`"Hello"`, `"a"`) → `nan` (0/0 mask means).
- Batch vs single: same text differs by ~2e-7 (GEMM noise) — below ±0.001 tolerance, but diff-test must compare like-for-like (batch vs batch, single vs single).
- `change_mode("bogus")` → `ValueError` (`detector.py:65-66`).
- Gradio demo enforces ≥64 tokens (`demo/demo.py:8,16-19`); core `compute_score` has no such guard — caller layer owns guards (AGENTS.md §6B: <150 words → "Too short to estimate").

**Observed trace values** (gpt2/distilgpt2, fp32, CPU, 4 threads): model load 25.8 s, RSS +964 MB; single score ≈4.4 s; HUMAN score 0.8449808359146118, capybara-AI 0.8428468704223633 (both below Falcon threshold → labelled AI — expected, tiny pair is not calibrated). ppl=3.2405474, x_ppl=3.8350544 for HUMAN. Truncation check: 0.614099264 both ways.

**transformers 5.x caveat:** `torch_dtype=` in `from_pretrained` is deprecated → `dtype=` (warning only; upstream code still works). Rebuild must handle both spellings.

## 5. Exact commands to resume / verify

```bash
# from C:\Users\varan\OneDrive\Desktop\ai_checker
.venv/Scripts/python.exe -c "import binoculars; print(binoculars.__file__)"
# → research/Binoculars/binoculars/__init__.py   (must point at the clone)

.venv/Scripts/python.exe research/trace_binoculars.py     # re-run the full trace (~1 min)
```
Upstream usage pattern (`research/Binoculars/main.py`): `from binoculars import Binoculars; bino = Binoculars(...); bino.compute_score(text); bino.predict(text)`.
Trace used: `Binoculars(observer_name_or_path="gpt2", performer_name_or_path="distilgpt2", use_bfloat16=False, max_token_observed=512, mode="low-fpr")`.

## 6. What happens next (only after user approval of 04-spec.md)

**Stage 5 for Binoculars** (rulebook §4, Step 1 gate):
1. Implement `detectors/binoculars.py` cleanly from `rea/binoculars/04-spec.md` (interface: `BinocularsDetector` with `compute_score`, `predict`, `change_mode`, plus project-side `score_window`; constants kept exact; extensions: per-model device overrides, optional `quantize` 8bit/4bit — NOT diff-tested against upstream).
2. Write `tests/diff_binoculars.py`: upstream (from `research/Binoculars`) vs rebuild on the **same 50 diverse samples**, same model pair/dtype/max_token_observed. Pass: `abs(diff) ≤ 0.001` per sample + identical `predict()` labels + identical batch ordering. Include short, near-512-token, batch-of-2, non-ASCII samples.
3. On this CPU-only machine use gpt2/distilgpt2 (already cached) unless the user provides GPU access for the Falcon pair. State the chosen pair explicitly in the test output.
4. Report results, then STOP before Repo #2 (`baoguangsheng/fast-detect-gpt`).

**Known risks for Stage 5:** numerical noise ~1e-7 between batch/single runs and between repeated forward passes (well under tolerance); empty-string/1-token behaviours must be replicated exactly (RuntimeError / nan); transformers version pinning — the venv has transformers 5.24.0 while upstream pins 4.31.0 (`requirements.txt:2`); keep the same version for both sides of the diff test.

## 7. Open items for the user (do not resolve unilaterally)

1. ~~Approval of `rea/binoculars/04-spec.md`~~ — **approved 2026-11-23; Stage 5 executed and PASSED.**
2. **Approval of `rea/fast-detect-gpt/04-spec.md`** — required before `detectors/fastdetect.py` / `tests/diff_fastdetect.py`. Key spec decisions to review: function-level diff test (upstream class raises `KeyError` for gpt2 pair), `classifier_params`/`use_float16`/`max_token_observed`/`quantize` extensions, no label/threshold (probability-only detector).
2. `rea-agents setup` needs Node ≥22.23.4 (machine has 22.14.0) — upgrade Node or skip registration?
3. GPU availability for the Falcon-7B pair (Stage 5 on this machine will use the small CPU pair; thresholds are Falcon-tuned and would need re-calibration for production per plan §7).
