# REA Stage 2 — Runtime & Stack: Fast-DetectGPT (Repo #2)

## Runtime & Dependencies

- **Machine:** Windows 10 x64, 16 GB RAM, **no NVIDIA GPU** — CPU-only, 4 torch threads.
- **Python:** 3.13.2, project venv `.venv/`.
- **Installed (verified this session):**
  - `torch 2.15.0+cpu`, `transformers 5.24.0`, `accelerate 1.16.0`, `numpy`, `psutil`
  - `scipy` (imported by `scripts/local_infer.py:15` but **missing from upstream
    `requirements.txt`** — dependency gap in upstream), `scikit-learn 1.9.1`,
    `matplotlib 3.11.2`, `datasets 5.2.0` — installed 2026-11-23 purely to satisfy the
    upstream import chain (see below).
- **Upstream pins (`research/fast-detect-gpt/requirements.txt`):** `transformers==4.28.1`
  (line 3), `datasets==2.12.0` (line 4), plus torch/numpy/matplotlib/tqdm/openai/nltk.
  We keep transformers 5.24.0 on **both sides** of any comparison (same policy as Repo #1).
  `torch_dtype=` in `scripts/model.py:46` triggers the transformers ≥5 deprecation warning
  (warning only; upstream code still runs).
- **Import chain caveat:** `local_infer.py:13-14` imports `model` and `fast_detect_gpt`;
  `fast_detect_gpt.py:13-15` imports `data_builder` (→ `datasets`, `custom_datasets`) and
  `metrics` (→ `matplotlib`, `sklearn`). So even function-level use of the criterion
  requires those four packages importable. They are experiment-harness dependencies, not
  scoring dependencies.

## Entry Points (exact files executed for the trace)

| Purpose | Entry point |
|---|---|
| Tokenizer/model loading | `scripts/model.py:41-54` (`load_model`), `:56-68` (`load_tokenizer`) |
| Analytic criterion | `scripts/fast_detect_gpt.py:52-70` (`get_sampling_discrepancy_analytic`) |
| Single-text pipeline | `scripts/local_infer.py:55-67` (`FastDetectGPT.compute_crit`), `:70-77` (`compute_prob`) |
| Probability mapping | `scripts/local_infer.py:20-24` (`compute_prob_norm`), params `:45-50` |
| Executed trace script | `research/trace_fastdetect.py` → output `research/trace_fastdetect_output.txt` |

Upstream CLI defaults: `--sampling_model_name falcon-7b --scoring_model_name
falcon-7b-instruct --device cuda` (`scripts/local_infer.py:104-106`). README.md:53 claims
gpt-neo-2.7B defaults — **stale**; the code is authoritative.

## Model Weights / Hardware Notes

- **Cached locally:** `gpt2`, `distilgpt2` (fp32). Trace uses **gpt2 as both scoring and
  sampling model** (single forward; `logits_ref = logits_score`, `local_infer.py:60-61`).
- **Not downloaded:** Falcon-7B pair (~28 GB fp16) and gpt-neo-2.7B (~10.8 GB fp32) —
  infeasible on this machine. Upstream loads the `float16_models` list
  (`scripts/model.py:35-36`) in fp16; gpt2 is not in the list → fp32.
- **Model alias table:** `scripts/model.py:19-34` (e.g. `falcon-7b` → `tiiuae/falcon-7b`);
  unknown names pass through unchanged (`:38-39`). `gpt-j` gets `revision='float16'`
  (`:47-48`); OPT uses the slow tokenizer (`:59-61`). Local override path
  `cache_dir/local.<name>` (`:12-16`).
- **Observed footprint (gpt2, fp32, CPU, 4 threads):** model load 17.3 s, RSS +627 MB;
  criterion ≈0.4–0.7 s per 50–80-token text; trace process final RSS 2146 MB (includes a
  second gpt2 load during the `FastDetectGPT` KeyError probe).
- **Sequence cap:** no `max_length` passed in `compute_crit` (`local_infer.py:56`) →
  tokenizer's `model_max_length` applies: **1024 for gpt2** (observed), 2048 for Falcon.