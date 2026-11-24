# REA Stage 1: Target Definition — Hello-SimpleAI/chatgpt-comparison-detection (HC3 RoBERTa)

## 1. Upstream Identity & Verification
* **Repository:** `Hello-SimpleAI/chatgpt-comparison-detection`
* **URL:** `https://github.com/Hello-SimpleAI/chatgpt-comparison-detection`
* **Cloned Commit:** `1f8c15c28f87e09a5abfd86ee6e15005dc7d2119` (2026-11-24)
* **Model Checkpoint:** `Hello-SimpleAI/chatgpt-detector-roberta` (HuggingFace Hub)
* **License:**
  * Code: MIT
  * Dataset: CC-BY-SA (used for training / calibration only, never redistributed)

## 2. Extraction Scope
* Rebuild single-text sequence classification scoring from `detect/dl_eval.py`.
* Provide sequence-length truncation (512 tokens) and calibrated softmax probability estimation.
* Expose clean interface `predict_window(text) -> {"probability": float, "is_ai": bool}`.
* Rebuild target file: `detectors/roberta_hc3.py`.
* Upgrade `detectors/ensemble.py` to 3-signal fusion:
  $$\text{logit}(p) = \beta_0 + \beta_1 \cdot \text{bino} + \beta_2 \cdot \text{fd} + \beta_3 \cdot \text{roberta}$$
  with graceful fallback to 2-signal when RoBERTa is disabled or offline.

## 3. Pass Conditions (Stage 5 Gate)
* `detectors/roberta_hc3.py` loads model weights cleanly on CPU with fp32.
* Accurately distinguishes human student writing from AI text.
* Graceful fallback when network or weights are absent.
