# REA Stage 3 — Evidence: Binoculars (Repo #1)

> Every behavioural claim below cites file:line at the checked-out commit
> `c8ae2f90d50ee696418bc71d8d9e5020e5f9d7b8`; citations are relative to the repo root
> `research/Binoculars/` (e.g. `binoculars/detector.py:87-96` =
> `research/Binoculars/binoculars/detector.py:87-96`). Observed outputs are from the
> local trace (`research/trace_binoculars.py`) with observer=`gpt2`,
> performer=`distilgpt2`, fp32, CPU, `max_token_observed=512`.

## 1. Execution Trace

### 1.1 Module import & global state
- `binoculars/__init__.py:1` re-exports `Binoculars` from `detector.py`.
- `detector.py:12` — `torch.set_grad_enabled(False)` globally disables gradients.
- `detector.py:20-21` — the two global thresholds (Falcon-7B pair, bfloat16-tuned):
  `BINOCULARS_ACCURACY_THRESHOLD = 0.9015310749276843`, `BINOCULARS_FPR_THRESHOLD = 0.8536432310785527`.
- `detector.py:23-24` — `DEVICE_1` = `cuda:0` if available else `cpu`; `DEVICE_2` = `cuda:1`
  only with ≥2 GPUs, else equals `DEVICE_1`.

### 1.2 Construction (`detector.py:28-58`)
1. `assert_tokenizer_consistency(observer, performer)` (`detector.py:35`,
   `utils.py:4-10`) compares `AutoTokenizer(...).vocab` of both model IDs and raises
   `ValueError` if vocabs differ. This is why observer/performer must share a tokenizer.
2. `change_mode(mode)` (`detector.py:37`, `detector.py:60-66`): `"low-fpr"` →
   FPR threshold, `"accuracy"` → accuracy threshold, anything else → `ValueError`.
   Default mode is `"low-fpr"` (`detector.py:33`).
3. Observer model: `AutoModelForCausalLM.from_pretrained(..., device_map={"": DEVICE_1},
   trust_remote_code=True, torch_dtype=bfloat16|float32, token=HF_TOKEN)`
   (`detector.py:38-44`); same for performer on `DEVICE_2` (`detector.py:45-51`).
   `use_bfloat16` default `True` (`detector.py:31`).
4. Both models `.eval()` (`detector.py:52-53`).
5. Tokenizer loaded from the **observer** (`detector.py:55`); if `pad_token` is None it is
   set to `eos_token` (`detector.py:56-57`) — gpt2-class tokenizers have no pad token.
6. `max_token_observed` default 512 (`detector.py:32`).

### 1.3 Tokenization (`detector.py:68-77`)
- Single string → wrapped into 1-element list (`detector.py:88`).
- `padding="longest"` **only when batch_size > 1**, else `False` (`detector.py:73`).
  → a single string is never padded; a batch pads to the longest member.
- `truncation=True`, `max_length=max_token_observed` (`detector.py:74-75`) — default
  transformers behaviour truncates on the right, i.e. **only the first 512 tokens are
  scored; the rest is silently dropped**.
- `return_token_type_ids=False` (`detector.py:76`); tensors moved to the observer device.

### 1.4 Logits (`detector.py:79-85`)
- `@torch.inference_mode()`; forward pass of both models on the same encodings
  (`detector.py:81-82`); `torch.cuda.synchronize()` only when not CPU (`detector.py:83-84`).

### 1.5 Score (`detector.py:87-96`)
```
ppl    = perplexity(encodings, performer_logits)          # detector.py:91
x_ppl  = entropy(observer_logits, performer_logits,       # detector.py:92-93
                 encodings, tokenizer.pad_token_id)
score  = ppl / x_ppl                                       # detector.py:94
```
Returns float for a single string, list for a list (`detector.py:96`).

### 1.6 Prediction (`detector.py:98-104`)
`score < threshold` → `"Most likely AI-generated"`, else `"Most likely human-generated"`
(`detector.py:100-103`). Lower score = more AI-like.

## 2. Mathematical & Algorithmic Details

### 2.1 `perplexity(encoding, logits, median=False, temperature=1.0)` (`metrics.py:9-27`)
- Shift logits left by one position and take labels = next token
  (`metrics.py:13-14`): teacher-forced causal CE over the sequence.
- Default branch (`median=False`): `mean CE = Σ_t ce_t·mask_t / Σ_t mask_t`
  (`metrics.py:23-24`), computed with `torch.nn.CrossEntropyLoss(reduction="none")`
  (`metrics.py:5`). Mask = attention mask shifted by one (`metrics.py:15`).
- **Despite the name, the returned value is mean CE in nats — there is NO `exp()`.**
  (`metrics.py:23-25`) The division `ppl/x_ppl` therefore compares two nats-scale
  quantities, not two perplexities.
- `median=True` branch (`metrics.py:17-20`) exists but is never used by the detector.

### 2.2 `entropy(p_logits, q_logits, encoding, pad_token_id, ...)` (`metrics.py:30-57`)
Called with `p` = observer logits, `q` = performer logits (`detector.py:92-93`).
- `p_proba = softmax(p_logits/temperature)` per position (`metrics.py:39-41`) — the
  observer's next-token distribution becomes the **soft target**.
- `ce = CrossEntropyLoss(q_scores, target=p_proba)` (`metrics.py:48`) with
  `q_scores = q_logits/temperature` (`metrics.py:46`): per-position
  `-Σ_v p_v · log softmax(q)_v` — the cross-entropy between observer and performer
  distributions, scored on the performer's logits.
- Averaged over non-pad positions only: `padding_mask = input_ids != pad_token_id`
  (`metrics.py:49,55`). Note this mask is per-token-ID (any position equal to the pad
  token id is excluded, even mid-text), unlike perplexity's attention-mask approach.
- `median`/`sample_p` branches (`metrics.py:43-44,51-53`) exist but are never enabled
  by the detector call.

### 2.3 Intuition (as implemented)
`score = mean-CE(performer predicting text) / mean-CE(observer-distribution || performer)`.
Machine text sits in the performer model's "easy" region (small numerator) while the
observer's distribution is far from the performer's (large denominator) → small score.
Human text raises the numerator more than the denominator → score closer to 1.
Observed control: with observer == performer (both `gpt2`) the denominator becomes the
model's own predictive entropy H(p) and the score equals CE/H ≈ 0.826 — **not 1.0**
(verified in the local trace; a naive "numerator == denominator" assumption is wrong).

### 2.4 Thresholds
Selected "using Falcon-7B and Falcon-7B-Instruct at bfloat16" (`detector.py:19`,
`README.md:29-31`): accuracy mode maximizes F1; low-fpr mode holds false-positive rate
≤ 0.01% (`demo/demo.py:96-99`).

## 3. Edge Cases Observed (local trace, gpt2/distilgpt2)

| Input | Behaviour | Where enforced |
|---|---|---|
| Single string | returns `float`; no padding applied | `detector.py:73,88,96` |
| List of strings | returns `list[float]`; `padding="longest"` | `detector.py:73,88,96` |
| Empty string `""` | **raises** `RuntimeError: cannot reshape tensor of 0 elements into shape [-1, 0] ...` inside `entropy()` (softmax/reshape on zero-length logits). Caller must reject empty input before scoring. | `metrics.py:41` (via `metrics.py:38-41`) |
| 1-token inputs (`"Hello"`, `"a"`) | returns **`nan`**: shifting leaves 0 positions, so both masks sum to 0 → `0/0` | `metrics.py:13-15,23-24`; `metrics.py:49,55` |
| 2+ token inputs | normal float score (e.g. `"The cat sat."` → 1.3756) | — |
| >512 tokens (1141 tested) | only first 512 tokens scored; `score(full) == score(first-512-tokens)` exactly (0.614099264) | `detector.py:74-75` (right truncation) |
| Batch with unequal lengths | shorter member padded with `pad_token_id` (= eos, 50256 for gpt2), excluded from both means | `detector.py:73`, `metrics.py:15,24,49,55` |
| Batch vs single run | same text scored in a batch differs from its single run by ~2e-7 (GEMM shape/kernel noise) — below the ±0.001 diff-test tolerance but must be compared like-for-like in Stage 5 | observed |
| Unknown mode string | `ValueError: Invalid mode: <mode>` | `detector.py:65-66` |
| Mismatched tokenizers | `ValueError` before model loading | `utils.py:4-10` |

Note: the upstream Gradio demo additionally refuses inputs under 64 tokens before
scoring (`demo/demo.py:8,16-19`); the core `compute_score` itself has no such guard —
the guard belongs to the caller layer.

## 4. Observed Outputs (local trace, 2026-11-23)

Environment: Windows 10 x64, CPU-only, torch 2.15.0+cpu, transformers 5.24.0,
`binoculars` importable from `research/Binoculars/binoculars/__init__.py` (editable
install), observer=`gpt2`, performer=`distilgpt2`, fp32, `max_token_observed=512`,
mode=`low-fpr`, 4 torch threads.

```
thresholds: accuracy=0.9015310749276843  low-fpr=0.8536432310785527
devices: cpu cpu
model load: 25.8s | RSS before=237MB after=1200MB (delta 964MB)
pad_token: <|endoftext|>  pad_token_id: 50256

score(HUMAN)    -> 0.8449808359146118   (float)
predict(HUMAN)  -> 'Most likely AI-generated'
score(AI_CAPY)  -> 0.8428468704223633   (float)
predict(AI_CAPY)-> 'Most likely AI-generated'
single-score time: 4.44s (incl. warmup)

batch [HUMAN, AI_CAPY] -> [0.8449806571006775, 0.8428471088409424]  (2.06s)
   (batch vs single differs by ~2e-7 — numerical noise, not logic)

score('Hello') -> nan      score('a') -> nan
score('The cat sat.') -> 1.3755987882614136
score('') -> RuntimeError (reshape of 0 elements, inside entropy())

long_text 1141 tokens: score(full)=0.614099264 == score(first-512-tokens)=0.614099264

change_mode('accuracy') -> threshold 0.9015310749276843
change_mode('bogus')    -> ValueError: Invalid mode: bogus

intermediates (recomputed on a fresh forward pass of HUMAN):
  ppl   (performer mean-CE)            = 3.2405474185943604
  x_ppl (cross-CE observer||performer) = 3.835054397583008
  ppl / x_ppl                          = 0.8449808223415742
  vs compute_score(HUMAN)              = 0.8449808359146118
  (agrees to ~1.4e-8 — residual is a second forward pass's CPU nondeterminism)

observer == performer (both gpt2): score = 0.8260813355445862
  (denominator is the model's predictive entropy H(p); CE/H, not 1.0)

RSS end: 1264MB (second model instance freed before measurement)
```

Threshold sanity: with this tiny model pair both test strings score ≈ 0.84 — below the
Falcon-tuned low-fpr threshold 0.8536 — so both are labelled "AI-generated". This is
expected: the gpt2/distilgpt2 pair is **not calibrated**; the thresholds are only valid
for the Falcon pair (`detector.py:19-21`).
