# REA Stage 3: Architectural Evidence — Hello-SimpleAI/chatgpt-comparison-detection

## 1. Upstream Logic Inspection
From `detect/dl_eval.py` lines 47–56:
```python
detector = pipeline("text-classification", model=checkpoint)
out = detector(batch['answer'], max_length=512, truncation=True)
batch['pred'] = [int(o['label'][-1]) for o in out]
```
The model outputs two classes:
* `LABEL_0`: Human text
* `LABEL_1`: ChatGPT text

Logits are normalized using softmax:
$$P(\text{AI}) = \frac{e^{z_1}}{e^{z_0} + e^{z_1}}$$

## 2. Window Truncation & Tokenization
* Input texts longer than 512 tokens must be truncated or processed via sliding windows.
* Tokenizer: `RobertaTokenizerFast.from_pretrained("Hello-SimpleAI/chatgpt-detector-roberta")`.
