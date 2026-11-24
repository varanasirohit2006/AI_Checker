# REA Stage 4 — Rebuild Spec: Fast-DetectGPT (Repo #2)

> **STAGE GATE: review required before implementation.** Do not create
> `detectors/fastdetect.py` until this spec is approved.

## Target Module Path

`detectors/fastdetect.py`

## Public Interface

```python
# detectors/fastdetect.py
DISTRIB_PARAMS = {  # exact upstream values (local_infer.py:45-50)
    "gpt-j-6B_gpt-neo-2.7B":        {"mu0": 0.2713,  "sigma0": 0.9366, "mu1": 2.2334, "sigma1": 1.8731},
    "gpt-neo-2.7B_gpt-neo-2.7B":    {"mu0": -0.2489, "sigma0": 0.9968, "mu1": 1.8983, "sigma1": 1.9935},
    "falcon-7b_falcon-7b-instruct": {"mu0": -0.0707, "sigma0": 0.9520, "mu1": 2.9306, "sigma1": 1.9039},
    "llama3-8b_llama3-8b-instruct": {"mu0": 0.1603,  "sigma0": 1.0791, "mu1": 2.4686, "sigma1": 2.1582},
}
DEFAULT_SAMPLING_MODEL = "falcon-7b"
DEFAULT_SCORING_MODEL = "falcon-7b-instruct"

def compute_prob_norm(x: float, mu0: float, sigma0: float,
                      mu1: float, sigma1: float) -> float
    # N(x;mu1,sigma1) / (N(x;mu0,sigma0) + N(x;mu1,sigma1)), scipy.stats.norm.pdf

class FastDetectGPTDetector:
    def __init__(
        self,
        sampling_model_name: str = DEFAULT_SAMPLING_MODEL,
        scoring_model_name: str = DEFAULT_SCORING_MODEL,
        device: str | None = None,          # default: cuda:0 if available else cpu
        use_float16: bool | None = None,    # None = upstream fp16-list rule (model.py:35-36)
        max_token_observed: int | None = None,  # None = tokenizer model_max_length (upstream)
        quantize: str | None = None,        # NEW: None | "8bit" | "4bit" (project requirement)
        classifier_params: dict | None = None,  # NEW: explicit {mu0,sigma0,mu1,sigma1} override
    ) -> None

    def compute_crit(self, text: str) -> tuple[float, int]   # (criterion, n_tokens - 1)
    def compute_prob(self, text: str) -> tuple[float, float, int]  # (prob, crit, ntoken)
    # project-side convenience (NOT in upstream):
    def score_window(self, text: str) -> dict  # {criterion, probability, n_tokens}
```

**No threshold / label exists upstream** — this detector outputs a probability only;
verdict wording belongs to the ensemble/caller layer (AGENTS.md §6D). `score_window`
therefore carries no `label` field (deliberate difference from `BinocularsDetector`).

## Step-by-Step Rebuild Logic

1. **Name resolution & loading** — keep upstream's alias table (`model.py:19-34`),
   pass-through for unknown names (`:38-39`), OPT slow-tokenizer rule (`:59-61`),
   `gpt-j` `revision="float16"` (`:47-48`). Load scoring model always; load a second
   sampling model **only if the names differ** (`local_infer.py:33-36`). `eval()` both;
   `torch.no_grad()` on forwards (`local_infer.py:58`). Handle transformers ≥5
   `torch_dtype`→`dtype` spelling. Extensions: `quantize` via BitsAndBytesConfig;
   `use_float16` override (None keeps the upstream fp16-list rule; CPU users should pass
   False — fp16 CPU inference is impractical, documented in the module docstring).
2. **Tokenizer contract** — from the scoring model; force `padding_side="right"`;
   `pad_token_id = eos_token_id` fallback; `'13b'`-in-name → `pad_token_id = 0`
   (`model.py:62-67`). Two-model mode: assert shifted token-id equality before scoring
   (`local_infer.py:64`).
3. **Classifier lookup** — key `f"{sampling_model_name}_{scoring_model_name}"` in
   `DISTRIB_PARAMS`; **raise `KeyError` for unknown pairs exactly like upstream**
   (`local_infer.py:51-52`) *unless* `classifier_params` override is given (project
   extension for re-calibrated pairs; NOT diff-tested). Lookup happens in `__init__`
   after model load, matching upstream failure order.
4. **Tokenize** — `truncation=True`, `return_tensors="pt"`, `padding=True`,
   `return_token_type_ids=False`; **no `max_length` by default** → tokenizer's
   `model_max_length` (1024 gpt2 / 2048 Falcon). `max_token_observed` override is an
   extension. `labels = input_ids[:, 1:]`; `logits = model(...).logits[:, :-1]`.
5. **Criterion (analytic)** — assert batch == 1; if vocab sizes differ, prefix-slice both
   logits to the min; `lprobs = log_softmax(score_logits)`; `p_ref = softmax(ref_logits)`;
   `ll = gather(lprobs, labels)`; `mean = Σ p_ref·lprobs`; `var = Σ p_ref·lprobs² − mean²`;
   **`crit = (Σ_t ll − Σ_t mean) / sqrt(Σ_t var)`** — sums over positions, then batch
   mean, then Python float. **No pad/attention masking, no temperature, no exp.**
6. **Probability** — `compute_prob_norm(crit, **params)`; return `(prob, crit, ntoken)`
   with `ntoken = labels.size(1)` (token count − 1).
7. **Edge behaviour (replicate, do not guard):** `""` → `RuntimeError` from the model
   forward (0-element view); 1-token → `nan`; list input → batch > 1 → `AssertionError`.
   Caller layer owns the <150-word guard and empty-input rejection.

## Confirmed vs. Unknowns

| # | Item | Status |
|---|---|---|
| 1 | Analytic criterion = summed log-likelihood gap / sqrt(summed variance); no masking | Confirmed `fast_detect_gpt.py:63-69` + trace |
| 2 | `ntoken = n_tokens − 1` | Confirmed `local_infer.py:57,67` + trace (70 → 69) |
| 3 | Truncation at tokenizer `model_max_length`, silently; crit(full) == crit(first-1024) | Confirmed `local_infer.py:56` + trace (1381 → 1023, exact equality) |
| 4 | Probability = balanced-prior two-Normal Bayes; high on BOTH tails; no threshold/label | Confirmed `local_infer.py:18-24,41` + trace (crit −5 → 0.983) |
| 5 | Unknown model pair → `KeyError` (e.g. `gpt2_gpt2`) | Confirmed `local_infer.py:51-52` + trace |
| 6 | Empty → `RuntimeError` (GPT-2 forward, transformers 5.24 `modeling_gpt2.py:549`); 1 token → `nan`; batch>1 → `AssertionError` | Verified by trace |
| 7 | Vocab-mismatch prefix-slice; two-model tokenizer-equality assert | Code-verified `fast_detect_gpt.py:56-60`, `local_infer.py:64`; not triggerable with gpt2/distilgpt2 (equal vocabs) — replicated from code, flagged as not trace-verified |
| 8 | Monte-Carlo variant (10 000 samples) | Out of scope; `local_infer.py:29` hard-wires analytic. Traced once (0.435188 vs 0.420045) |
| 9 | fp16-list loading rule, alias table, OPT/gpt-j/13b special cases | Confirmed `model.py:19-36,47-48,59-67`; only gpt2 path trace-verified on this machine |
| 10 | Quantization + `classifier_params` + `max_token_observed` + `use_float16` overrides | Project extensions; NOT diff-tested against upstream numbers |
| 11 | `scipy` missing from upstream requirements; transformers 4.28.1 pin vs our 5.24.0 | Confirmed `requirements.txt:3`, `local_infer.py:15`; same-version policy as Repo #1 |

## Acceptance (Stage 5, run only after this spec is approved)

`tests/diff_fastdetect.py`, **gpt2 scoring==sampling, fp32, CPU** (stated in test output):

- **Criterion:** 50 diverse texts (human/AI/mixed; short, near/over-1024-token,
  non-ASCII, special formats). Upstream side executes the clone's own
  `load_tokenizer`/`load_model` + the exact `compute_crit` pipeline
  (`local_infer.py:56-66`) + `get_sampling_discrepancy_analytic`; rebuild side uses
  `FastDetectGPTDetector.compute_crit`. Pass: `abs(diff) ≤ 0.001` per text.
  (The upstream *class* cannot instantiate with gpt2 — `KeyError` — so the diff test
  compares the function-level pipeline the class itself calls; see `01-target.md`.)
- **Probability:** `compute_prob_norm` (upstream import) vs rebuild on all 50 criterion
  values × **all four published parameter sets**: `abs(diff) ≤ 0.001`.
- **Edges:** `""` → same exception type; 1-token → `nan` both; batch>1 →
  `AssertionError` both; unknown-pair `KeyError`; truncation-equivalence at 1024.
- **`score_window` consistency:** criterion/probability match `compute_prob`,
  `n_tokens == ntoken + 1`.
- License: MIT attribution recorded in `THIRD_PARTY_LICENSES.md` (done); module header
  carries the MIT notice reference; no upstream code copied verbatim.