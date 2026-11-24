# REA Stage 2: Stack & Dependencies — Hello-SimpleAI/chatgpt-comparison-detection

## 1. Upstream Dependencies
* `torch >= 1.10.0`
* `transformers >= 4.20.0`
* `datasets`
* `scikit-learn`

## 2. In-Tree Rebuild Dependencies
* Standard PyTorch (`torch`) + HuggingFace Transformers (`transformers`).
* No novel or specialized C-extensions required.
* Base architecture: `RobertaForSequenceClassification` with 2 output logits:
  * Class 0: Human
  * Class 1: ChatGPT / AI

## 3. Memory & Hardware Requirements
* `roberta-base` checkpoint is ~498 MB.
* Runs on CPU with fp32 in ~0.3s per 250-word window.
