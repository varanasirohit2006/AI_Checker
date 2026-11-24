# REA Stage 1 — Target: Binoculars (Repo #1)

## Upstream Repository

| Field | Value |
|---|---|
| URL | https://github.com/ahans30/Binoculars |
| Commit checked out in `research/Binoculars` | `c8ae2f90d50ee696418bc71d8d9e5020e5f9d7b8` (2024-05-14, "Merge pull request #13 from githubbuhtig10/fix-config-import") |
| License | BSD-3-Clause — verified in `research/Binoculars/LICENSE.md:1-28` (© 2023 Abhimanyu Hans, Avi Schwarzschild, Tom Goldstein). Recorded in `THIRD_PARTY_LICENSES.md`. |
| Paper | "Spotting LLMs With Binoculars: Zero-Shot Detection of Machine-Generated Text", arXiv:2401.12070 |
| Upstream package | `binoculars` (setup.py declares version 0.0.10) |

## Exact Feature Scope

Rebuild the **Binoculars zero-shot score function** and its **thresholded prediction** as implemented in
`research/Binoculars/binoculars/detector.py` and `research/Binoculars/binoculars/metrics.py`:

1. **`Binoculars.compute_score(input_text)`** (`detector.py:87-96`) — returns one float per input string:
   `score = ppl / x_ppl` where
   - `ppl` = mean cross-entropy of the **performer** LM predicting the text (`metrics.py:9-27` — despite the name, this returns mean CE in nats, not exp(CE));
   - `x_ppl` = mean cross-entropy between the **observer** model's next-token probability distribution and the **performer** model's logits (`metrics.py:30-57`).
2. **`Binoculars.predict(input_text)`** (`detector.py:98-104`) — `score < threshold` → `"Most likely AI-generated"`, else `"Most likely human-generated"`.
3. **Two fixed global thresholds** (`detector.py:19-21`):
   - `BINOCULARS_ACCURACY_THRESHOLD = 0.9015310749276843` (optimized for F1)
   - `BINOCULARS_FPR_THRESHOLD = 0.8536432310785527` (low-fpr, chosen at 0.01% FPR)
   - selected with Falcon-7B / Falcon-7B-Instruct at bfloat16; mode switch via `change_mode()` (`detector.py:60-66`).
4. **Tokenization contract** (`detector.py:68-77`): single string → no padding; batch > 1 → `padding="longest"`; `truncation=True`, `max_length=max_token_observed` (default 512); tokenizer taken from the observer model with `pad_token = eos_token` fallback (`detector.py:55-57`).

## Out of Scope

- `app.py` / `demo/demo.py` Gradio UI, HTML/CSS, and logo assets (`research/Binoculars/assets/*`).
- `experiments/` (evaluation harness: `run.py`, `jobs.sh`, `utils.py`).
- `datasets/` calibration/eval JSONL files (CC-News, CNN, PubMed, OpenOrca).
- Anything not reachable from `compute_score`/`predict` (e.g., `metrics.py` `median=` and `sample_p=` branches are read for reference but the default code path never enables them — `detector.py:91-93`).
- Model weights themselves are downloaded at runtime from the Hugging Face hub; they are not part of the rebuild.

## Stage 5 Pass Condition

Run the rebuilt module (`detectors/binoculars.py`) and the upstream package (imported from
`research/Binoculars`) on the **same 50 text samples** with the **same model pair, dtype, tokenizer and
`max_token_observed`** (per plan: Falcon pair if hardware allows, otherwise an identical agreed-on CPU pair).
For every sample:

```
abs(score_upstream - score_rebuild) <= 0.001
```

and additionally for every sample: identical `predict()` label (both sides apply the same threshold/mode),
and for list inputs, identical list ordering and length. Batch path (`batch_size > 1`) must also be
diff-tested with the same tolerance.
