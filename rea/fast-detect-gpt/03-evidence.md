# REA Stage 3 — Evidence: Fast-DetectGPT (Repo #2)

All citations refer to `research/fast-detect-gpt/` at commit
`971b05202bac2bb504d60c0ac0812fea7a8f7c82`. Observed values come from
`research/trace_fastdetect.py` (output: `research/trace_fastdetect_output.txt`),
executed 2026-11-23 on CPU, gpt2 scoring==sampling, fp32, 4 torch threads,
transformers 5.24.0.

## 1. Execution Trace (single text → criterion → probability)

1. **Tokenizer load** — `load_tokenizer` (`scripts/model.py:56-68`): alias resolution
   (`:57`, table `:19-34`), `padding_side='right'` forced (`:62`), and if
   `pad_token_id is None` it is set to `eos_token_id` (`:64-65`); models with `'13b'` in
   the name get `pad_token_id = 0` instead (`:66-67`).
   **Observed:** gpt2 → `padding_side='right'`, `pad_token_id=50256`,
   `eos_token_id=50256`, `model_max_length=1024`.
2. **Model load** — `load_model` (`scripts/model.py:41-54`): fp16 **only** for names in
   `float16_models` (`:35-36`, applied `:45-46`); `gpt-j` pinned to `revision='float16'`
   (`:47-48`); `model.to(device)` (`:52`). gpt2 → fp32. `eval()` is called by the detector
   (`scripts/local_infer.py:32`).
3. **Tokenize** — `compute_crit` (`scripts/local_infer.py:56`):
   `tokenizer(text, truncation=True, return_tensors="pt", padding=True,
   return_token_type_ids=False)`. **No `max_length` argument** → truncation happens at the
   tokenizer's `model_max_length` (1024 for gpt2). Single string + `padding=True` → no
   padding actually applied.
4. **Shift** — `labels = tokenized.input_ids[:, 1:]` (`local_infer.py:57`);
   `logits_score = scoring_model(**tokenized).logits[:, :-1]` (`:59`) under
   `torch.no_grad()` (`:58`).
5. **Reference logits** — if `sampling_model_name == scoring_model_name`,
   `logits_ref = logits_score` (same tensor, `local_infer.py:60-61`). Otherwise the
   sampling tokenizer re-tokenizes and **asserts token-id equality**
   (`:63-64`, `"Tokenizer is mismatch."`), then a second forward gives `logits_ref` (`:65`).
6. **Criterion** — `get_sampling_discrepancy_analytic(logits_ref, logits_score, labels)`
   (`local_infer.py:66` → `fast_detect_gpt.py:52-70`), math in §2.
7. **Return** — `(crit, labels.size(1))` (`local_infer.py:67`): **ntoken = token count − 1**
   (observed: 70 raw tokens → ntoken 69).
8. **Probability** — `compute_prob` (`local_infer.py:70-77`) looks up
   `distrib_params[f'{sampling_model_name}_{scoring_model_name}']` (`:51-52`) and calls
   `compute_prob_norm(crit, mu0, sigma0, mu1, sigma1)` (`:76`), math in §3.

## 2. Mathematical Details — analytic criterion

`scripts/fast_detect_gpt.py:52-70`, batch size asserted == 1 (`:53-55`):

- **Vocab mismatch handling** (`:56-60`): if ref/score vocab sizes differ, **both logits
  are sliced to `min(vocab_ref, vocab_score)`** (prefix truncation, no warning printed —
  the print is commented out at `:57`).
- `labels` unsqueezed to `(1, T, 1)` if needed (`:62`).
- `lprobs_score = log_softmax(logits_score, dim=-1)` (`:63`).
- `probs_ref = softmax(logits_ref, dim=-1)` (`:64`).
- Per-position log-likelihood of the true token:
  `log_likelihood = lprobs_score.gather(-1, labels).squeeze(-1)` (`:65`).
- Per-position expectation under the reference distribution:
  `mean_ref = Σ_v probs_ref · lprobs_score` (`:66`).
- Per-position variance:
  `var_ref = Σ_v probs_ref · lprobs_score² − mean_ref²` (`:67`).
- **Document-level aggregation (sums, NOT means, over positions):**
  `discrepancy = (Σ_t log_likelihood − Σ_t mean_ref) / sqrt(Σ_t var_ref)` (`:68`),
  then `.mean()` over the batch dim (`:69`, trivial for batch 1) and `.item()` (`:70`).
- **No attention-mask or pad-token masking anywhere** — every shifted position counts
  (contrast with Binoculars). No temperature parameter. When ref == score, `mean_ref` is
  the model's predictive entropy term and `var_ref` its log-prob variance.
- Higher criterion ⇒ text is *more* surprising under the model's own sampling
  distribution ⇒ more machine-like (paper convention; observed AI text 1.607 vs human
  −0.296 below).

**Observed values (gpt2, fp32):**

| Sample | crit | ntoken | prob (falcon params) |
|---|---|---|---|
| HUMAN (bike commute) | −0.2959312201 | 69 | 0.108989 |
| AI (productivity boilerplate) | 1.6073263884 | 53 | 0.649947 |
| NON_ASCII (French) | 1.0482848883 | 78 | 0.379650 |

- **Determinism:** repeated HUMAN run → −0.295931220055 both times, bit-identical.
- **Monte-Carlo variant (out of scope):** `get_sampling_discrepancy`
  (`fast_detect_gpt.py:34-50`) draws **10 000 samples** (`:20`) from
  `Categorical(log_softmax(logits_ref))` (`:21-23`) and z-scores the true log-likelihood
  against the sample mean/std (`:47-49`). Observed on "The cat sat on the mat." with
  `torch.manual_seed(0)`: sampling 0.435188 vs analytic 0.420045 — same quantity, MC noise.
  `local_infer.py:29` hard-wires the **analytic** variant.

## 3. Mathematical Details — probability mapping

`scripts/local_infer.py:18-24`: balanced-prior Bayes with two Normal densities:

```
p(AI | crit) = N(crit; mu1, sigma1) / (N(crit; mu0, sigma0) + N(crit; mu1, sigma1))
```

implemented with `scipy.stats.norm.pdf` (`:21-23`). Parameter table (`:45-50`):

| key (`sampling_scoring`) | mu0 | sigma0 | mu1 | sigma1 |
|---|---|---|---|---|
| gpt-j-6B_gpt-neo-2.7B | 0.2713 | 0.9366 | 2.2334 | 1.8731 |
| gpt-neo-2.7B_gpt-neo-2.7B | −0.2489 | 0.9968 | 1.8983 | 1.9935 |
| falcon-7b_falcon-7b-instruct | −0.0707 | 0.9520 | 2.9306 | 1.9039 |
| llama3-8b_llama3-8b-instruct | 0.1603 | 1.0791 | 2.4686 | 2.1582 |

- Design note: `sigma1 = 2·sigma0` for wider AI coverage (`:39-40`); parameters were
  fit on dev samples per pair (comment `:37-44`, acc 0.81–0.89).
- **Both-tails caveat** (`:41`): probability is high on *both* sides of Normal(mu0, sigma0).
  **Observed:** crit −5 → 0.982646, crit 0 → 0.132964, crit 2.9306 → 0.986298,
  crit 10 → ~1.0. Very *human-atypical* text also reads as "AI" under this mapping.
- **Unknown pair → `KeyError`** at `:52`. **Observed:** `FastDetectGPT` with
  `gpt2/gpt2` raises `KeyError: 'gpt2_gpt2'` (models load first, then the lookup fails).
  There is **no threshold and no label** anywhere in this repo — only a probability.

## 4. Edge Cases Observed

| Input | Behaviour | Citation / origin |
|---|---|---|
| `""` (0 tokens) | `RuntimeError: cannot reshape tensor of 0 elements into shape [-1, 0]` — raised **inside GPT-2 forward** (`transformers 5.24.0 modeling_gpt2.py:549`, `input_ids.view(-1, input_shape[-1])`), before the criterion is reached | trace §edge cases; tokenizer yields shape (1, 0) |
| `"Hello"` / `"a"` (1 token) | `crit = nan`, ntoken 0 — shifted sums are 0, `0 / sqrt(0)` | `fast_detect_gpt.py:68`; trace |
| `"Hello world"` (2 tokens) | finite crit −0.6289188266, ntoken 1 | trace |
| batch > 1 into criterion | `AssertionError` (batch must be 1) | `fast_detect_gpt.py:53-55`; trace |
| 1381-token text | truncated to 1024; crit 4.0256905556 **exactly equal** to crit of `decode(first 1024 tokens)`; ntoken 1023 | `local_infer.py:56` (`truncation=True`, no max_length); trace |
| >1024 tokens tokenizer call | transformers warning "Token indices sequence length is longer than…" (warning only) | trace |
| mismatched tokenizers (two-model mode) | `AssertionError "Tokenizer is mismatch."` if shifted ids differ | `local_infer.py:64` (code-verified; not triggerable with gpt2/distilgpt2 — identical vocab) |
| vocab-size mismatch | silent prefix-slice of both logits to min vocab | `fast_detect_gpt.py:56-60` (code-verified; gpt2 pair has equal vocabs) |

- **No length guard in the core.** The demo only prints "the longer text has more
  reliable result" (`local_infer.py:84`). The <150-word guard (AGENTS.md §6B) belongs to
  our caller layer, as with Binoculars.
- **No empty-input guard either** — callers must reject empty text (it raises, §4).

## 5. Confirmed Environment Caveats

- transformers 5.24.0 vs upstream pin 4.28.1 (`requirements.txt:3`): `torch_dtype=`
  deprecation warning from `scripts/model.py:46` (warning only). Both sides of any diff
  test run the same installed version.
- `scipy` is required by `local_infer.py:15` but absent from upstream
  `requirements.txt` — installed in our venv.
- `datasets 5.2.0` / `scikit-learn 1.9.1` / `matplotlib 3.11.2` installed only to satisfy
  the experiment-harness import chain (`fast_detect_gpt.py:13-15`); none are used by the
  scoring path itself.