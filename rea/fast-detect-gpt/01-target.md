# REA Stage 1 — Target: Fast-DetectGPT (Repo #2)

## Upstream Repository

- **URL:** https://github.com/baoguangsheng/fast-detect-gpt
- **Commit checked out in `research/fast-detect-gpt`:** `971b05202bac2bb504d60c0ac0812fea7a8f7c82` (2026-02-07, "Update README.md")
- **License:** MIT — verified in `research/fast-detect-gpt/LICENSE` (© 2023 Bao Guangsheng); recorded in `THIRD_PARTY_LICENSES.md` on 2026-11-23. Per-file headers also carry the MIT notice (e.g. `scripts/local_infer.py:1-4`).
- **Paper:** "Fast-DetectGPT: Efficient Zero-Shot Detection of Machine-Generated Text via Conditional Probability Curvature", ICLR 2024 (arXiv:2310.05130). README.md:2-4.

## Exact Feature Scope

Rebuild into `detectors/fastdetect.py` (plan §4.3 row 2):

1. **Analytic conditional-probability-curvature criterion** —
   `get_sampling_discrepancy_analytic(logits_ref, logits_score, labels)`
   (`scripts/fast_detect_gpt.py:52-70`): per-position log-likelihood of the true next
   token under the scoring model, minus its expectation under the sampling model's
   distribution, normalized by the sqrt of the summed predictive variance.
2. **Single-text scoring pipeline** — `FastDetectGPT.compute_crit`
   (`scripts/local_infer.py:55-67`): tokenize → shift labels/logits → forward →
   criterion; returns `(crit, ntoken)` where `ntoken = n_tokens − 1`.
3. **Score-to-probability mapping** — `compute_prob_norm`
   (`scripts/local_infer.py:20-24`) with the four published Normal-distribution
   parameter sets (`scripts/local_infer.py:45-50`), and `FastDetectGPT.compute_prob`
   (`scripts/local_infer.py:70-77`).
4. **Model/tokenizer loading contract** — `scripts/model.py:41-68` (fp16 list,
   right padding, pad-token fallback, alias table).

## Out of Scope

- Experiment harnesses: `scripts/fast_detect_gpt.py:experiment` (dataset ROC/PR
  evaluation), `scripts/detect_gpt.py`, `dna_gpt.py`, `detect_llm.py`, `baselines.py`,
  `supervised.py`, `gptzero.py`, `paraphrasing.py`, `data_builder.py`,
  `custom_datasets.py`, `metrics.py`, `report_results.py`, `show_result.py`,
  `data_truncator.py`; all `*.sh` experiment scripts; `exp_main/`, `exp_gpt3to4/`, `doc/`.
- The **Monte-Carlo** variant `get_sampling_discrepancy` / `get_samples`
  (`scripts/fast_detect_gpt.py:17-50`, 10 000 samples) — `local_infer.py:29` hard-wires
  the analytic variant; traced once for evidence only.
- Interactive CLI loop `run()` (`scripts/local_infer.py:81-100`) — caller layer owns UX.
- Training/supervised detectors and the online demo.

## Stage 5 Pass Condition

`tests/diff_fastdetect.py`, same model on both sides (CPU pair: **gpt2**, scoring ==
sampling, fp32 — see `02-stack.md`):

- **Criterion:** `abs(crit_upstream − crit_rebuild) ≤ 0.001` on **50 diverse texts**
  (human/AI/mixed, short, near/over the 1024-token cap, non-ASCII, special formats).
  Upstream side runs the exact `compute_crit` pipeline (`local_infer.py:56-66`) using
  the clone's `load_tokenizer`/`load_model`/`get_sampling_discrepancy_analytic`.
- **Probability:** identical mapping on all 50 criterion values for **each of the four
  published parameter sets** (`abs(prob diff) ≤ 0.001`; pure function, no models).
- **Edge behaviours replicated:** empty/1-token inputs, batch>1 assertion, unknown
  model-pair `KeyError`, truncation at `model_max_length`.
- Note: upstream `FastDetectGPT.__init__` raises `KeyError` for pairs absent from
  `distrib_params` (e.g. `gpt2_gpt2`), so the end-to-end class path cannot run with the
  CPU pair; the diff test therefore compares the function-level pipeline that the class
  itself calls, plus the probability mapping separately. This is documented in `04-spec.md`.