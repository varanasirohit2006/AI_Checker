# REA Stage 2 — Stack Recon: Binoculars (Repo #1)

## Runtime & Dependencies

| Item | Upstream (research/Binoculars) | Local execution environment |
|---|---|---|
| Python | 3.9 ("developed and tested with" — `README.md:18`) | 3.13.2 in project venv `.venv/` |
| transformers | pinned to v4.31.0 via URL in `requirements.txt:2` | latest (see below) — code path identical for gpt2-class models |
| torch | pulled by `transformers[torch]` (`requirements.txt:2`) | CPU wheel (no NVIDIA GPU on this machine; `nvidia-smi` absent) |
| sentencepiece | `requirements.txt:1` | installed (needed for Falcon tokenizer) |
| Other pinned deps | datasets, numpy, gradio, gradio_client, scikit-learn, seaborn, pandas (`requirements.txt:3-8`) | not installed — out of scope for `compute_score` trace |
| Package install | `pip install -e .` (`README.md:24`) | `pip install -e research/Binoculars --no-deps` (executes the exact cloned code) |

Upstream package metadata: `setup.py:1-15` (name `Binoculars`, version `0.0.10`,
license read from `LICENSE.md`).

## Model Weights

| Role | Default (upstream) | Loaded in our local trace |
|---|---|---|
| Observer | `tiiuae/falcon-7b` (`detector.py:29`) | `gpt2` (124M params, fp32 ≈ 500 MB) |
| Performer | `tiiuae/falcon-7b-instruct` (`detector.py:30`) | `distilgpt2` (82M params, fp32 ≈ 350 MB) |

Both upstream defaults load with `trust_remote_code=True` and
`torch.bfloat16` by default (`detector.py:38-51`). Falcon pair needs ≈ 28 GB in
bf16 — unavailable on this 16 GB RAM / no-GPU machine, so the trace uses the
smallest pair that shares a tokenizer (both gpt2-family → `assert_tokenizer_consistency`
passes, `utils.py:4-10`). **Consequence:** the numeric thresholds (Falcon-tuned) are
cited but not re-derived; our rebuild keeps them as configuration constants.

## Entry Points (exact files/functions executed locally)

1. `research/Binoculars/binoculars/__init__.py:1` → `from .detector import Binoculars`.
2. `detector.py:27` `Binoculars.__init__` → tokenizer-consistency assert (`utils.py:4-10`),
   mode/threshold selection (`detector.py:37`, `detector.py:60-66`), loads both models
   (`detector.py:38-51`), tokenizer from observer + pad fallback (`detector.py:55-57`).
3. `detector.py:87` `compute_score` → `_tokenize` (`detector.py:68-77`) →
   `_get_logits` (`detector.py:79-85`) → `metrics.perplexity` (`metrics.py:9-27`) →
   `metrics.entropy` (`metrics.py:30-57`) → `score = ppl / x_ppl` (`detector.py:94`).
4. `detector.py:98` `predict` → threshold compare (`detector.py:100-103`).
5. Repro driver: `research/trace_binoculars.py` (this workspace, gitignored) and the
   upstream `main.py:1-14` (documented reference output `0.75661373` for the capybara
   sample with the Falcon pair — not reproducible on this hardware).

## Hardware / VRAM Notes

- Machine: Windows 10 x64, 16 GB RAM, **no GPU** → both models run on CPU
  (`detector.py:23-24` degrades `DEVICE_1=DEVICE_2="cpu"`).
- Observed local footprint (gpt2 + distilgpt2, fp32, `torch.set_num_threads(4)`,
  trace of 2026-11-23): model load 25.8 s, RSS 237 MB → 1200 MB (delta ≈ 964 MB);
  single-score call ≈ 4.4 s (incl. warmup), batched call ≈ 2.1 s; RSS ≈ 1.26 GB at end
  of the full edge-case trace. Full details in `03-evidence.md` §4.
- Upstream defaults (Falcon-7B ×2, bf16) require ≈ 28 GB VRAM/RAM; the plan's
  budget option (8-bit/4-bit quantization or smaller pairs) applies to our rebuild.
- Logits for a 512-token window are `512 × vocab(50257) × 4 B ≈ 103 MB` per model —
  keep `max_token_observed` at 512 and window longer texts in the caller.
- Environment caveat: transformers 5.24.0 deprecates `torch_dtype=` in favour of
  `dtype=` in `from_pretrained` (warning emitted during the trace); upstream code at
  `detector.py:41-42,48-49` still works. Our rebuild must tolerate both spellings
  across transformers versions.
