# REA Stage 4 — Rebuild Spec: Binoculars (Repo #1)

> **STAGE GATE: APPROVED.** User completed review and authorized Stage 5 on
> 2026-11-23. Implementation: `detectors/binoculars.py`; differential test:
> `tests/diff_binoculars.py`.

## Target Module Path

`detectors/binoculars.py`

## Public Interface

```python
# detectors/binoculars.py
class BinocularsDetector:
    def __init__(
        self,
        observer_name_or_path: str = "tiiuae/falcon-7b",
        performer_name_or_path: str = "tiiuae/falcon-7b-instruct",
        use_bfloat16: bool = True,          # False on CPU
        max_token_observed: int = 512,
        mode: str = "low-fpr",              # "low-fpr" | "accuracy"
        device_observer: str | None = None, # optional per-model device override
        device_performer: str | None = None,
        quantize: str | None = None,        # NEW: None | "8bit" | "4bit" (project requirement)
    ) -> None

    def change_mode(self, mode: str) -> None
    def compute_score(self, input_text: str | list[str]) -> float | list[float]
    def predict(self, input_text: str | list[str]) -> str | list[str]
    # project-side convenience (NOT in upstream):
    def score_window(self, text: str) -> dict   # {score, label, ppl, x_ppl, n_tokens}
```

Constants (exact upstream values, kept as module constants):

```python
BINOCULARS_ACCURACY_THRESHOLD = 0.9015310749276843
BINOCULARS_FPR_THRESHOLD     = 0.8536432310785527
DEFAULT_OBSERVER  = "tiiuae/falcon-7b"
DEFAULT_PERFORMER = "tiiuae/falcon-7b-instruct"
DEFAULT_MAX_TOKEN_OBSERVED = 512
```

## Step-by-Step Rebuild Logic

1. **Tokenizer contract** — load the observer model's tokenizer; if it has no pad
   token, set `pad_token = eos_token`. Before loading models, verify observer and
   performer tokenizer vocabs are equal; raise `ValueError` otherwise.
2. **Model loading** — load observer and performer causal LMs with
   `trust_remote_code=True`, fp32 when `use_bfloat16=False`; place each on its device.
   `eval()` both; disable gradients (`torch.inference_mode()` on the forward pass).
   Handle the transformers ≥5.x `torch_dtype`→`dtype` deprecation (pass whichever the
   installed version accepts). Extension: if `quantize` is set, load with bitsandbytes
   8-bit/4-bit config on the same device.
3. **Tokenize** — `return_tensors="pt"`, `truncation=True`,
   `max_length=max_token_observed`, `return_token_type_ids=False`; apply
   `padding="longest"` **only** when the batch has more than one item.
4. **Perplexity term (numerator)** — shift logits left by one; labels = tokens shifted
   right; elementwise CE with `reduction="none"`; mask by shifted attention mask;
   `mean = Σ(ce·mask) / Σ(mask)`. **Return the mean CE in nats — do NOT exponentiate.**
5. **Cross-entropy term (denominator)** — softmax of observer logits per position
   (soft targets); elementwise `CrossEntropyLoss(performer_logits, target=observer_probs)`;
   mask out positions whose token id equals `pad_token_id`;
   `mean = Σ(ce·mask) / Σ(mask)`.
6. **Score** — `score = numerator / denominator`; float for a single string, list for
   a list.
7. **Predict** — `score < threshold` → `"Most likely AI-generated"` else
   `"Most likely human-generated"`. Default mode `"low-fpr"`.

## Confirmed vs. Unknowns

| # | Item | Status |
|---|---|---|
| 1 | Mean-CE (nats) division — no exp() anywhere in the score | Confirmed by `metrics.py:23-25,55` + local trace |
| 2 | Single-string input is never padded; batch >1 uses `padding="longest"` | Confirmed `detector.py:73` + trace |
| 3 | Only the first 512 tokens are scored; the rest is silently truncated | Confirmed `detector.py:74-75` + trace (truncation-equivalence check) |
| 4 | Thresholds are Falcon-pair-specific and are kept as config constants | Confirmed `detector.py:19-21`; re-calibration needed if our default model pair changes (project requirement, per plan §7 Model size note) |
| 5 | `median=` and `sample_p=` branches of both metric functions are dead code in the detection path | Confirmed — detector never passes them (`detector.py:91-93`) |
| 6 | Empty-string behaviour | **Verified by trace**: empty string raises `RuntimeError` inside `entropy()` (reshape of 0-element logits); 1-token inputs return `nan` (0/0 mask mean). Our module must replicate both behaviours bit-for-bit (the caller layer, not this module, enforces the <150-word guard from AGENTS.md §6B and the demo's 64-token minimum) |
| 7 | Non-English / non-Latin text: upstream warns it degrades (defaults toward "human") | Documented in `demo/demo.py:106`; our caller layer (not this module) attaches the confidence warning |
| 8 | `DEVICE_2` only differs from `DEVICE_1` with ≥2 GPUs | Confirmed `detector.py:23-24`; our rebuild adds explicit per-model device overrides |
| 9 | Quantization (4-bit/8-bit) is a project requirement not present upstream | Our extension; scores with quantized weights are **not** diff-tested against upstream fp16 numbers — flagged in the module docstring |
| 10 | Upstream default bfloat16 on CPU | Our module must refuse bfloat16 on CPU (upstream would fail there anyway) with a clear error |

## Acceptance (Stage 5, run only after this spec is approved)

- `tests/diff_binoculars.py` imports upstream from `research/Binoculars` and our module
  from `detectors/binoculars.py`, same model pair/dtype/`max_token_observed`.
- 50 diverse samples (human/AI/mixed; incl. short, near-512-token, batch of 2,
  non-ASCII): `abs(score_upstream - score_rebuild) ≤ 0.001` and identical `predict()`
  labels; batch outputs identical in order.
- License notice: BSD-3-Clause attribution for Binoculars is recorded in
  `THIRD_PARTY_LICENSES.md` (already done); if any upstream block is adapted directly,
  its notice is reproduced in the module header.
