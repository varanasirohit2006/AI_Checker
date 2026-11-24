# REA Stage 4: Rebuild Specification — RoBERTa HC3 Detector

## 1. Module Architecture (`detectors/roberta_hc3.py`)
* Class: `RobertaHC3Detector`
  * `__init__(model_name_or_path: str = "Hello-SimpleAI/chatgpt-detector-roberta", device: str = "cpu")`
  * `score_text(text: str) -> dict[str, float]`
    * Encodes text up to 512 tokens.
    * Computes forward pass with `torch.no_grad()`.
    * Applies `softmax(dim=-1)` to logits.
    * Returns `{"ai_probability": prob_class_1, "human_probability": prob_class_0, "predicted_label": "ai" | "human"}`.
  * Robust fallback: if remote download fails or model is not cached, provides calibrated keyword heuristic fallback so offline execution never crashes.

## 2. Integration into `detectors/ensemble.py`
* 3-signal combiner:
  $$z = \beta_0 + \beta_1 \cdot \text{bino} + \beta_2 \cdot \text{fd} + \beta_3 \cdot \text{roberta}$$
* Seamless fallback: if RoBERTa signal is None or model is omitted, reverts automatically to the calibrated 2-signal model.
