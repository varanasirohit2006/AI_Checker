"""Fast-DetectGPT detector — clean REA rebuild of baoguangsheng/fast-detect-gpt.

Upstream: https://github.com/baoguangsheng/fast-detect-gpt (MIT, commit
971b05202bac2bb504d60c0ac0812fea7a8f7c82). Full license text and attribution
are recorded in THIRD_PARTY_LICENSES.md. Behaviour rebuilt from
rea/fast-detect-gpt/04-spec.md; no upstream code copied verbatim.

Criterion = analytic conditional-probability-curvature score (log-likelihood
gap between scoring model and reference sampling model, normalized by the
square root of summed predictive variance).
Probability = balanced-prior two-Normal Bayes mapping using dev-calibrated
distribution parameters (mu0, sigma0 for human; mu1, sigma1 for AI).

Extensions beyond upstream:
- Per-model device / quantization overrides (8-bit, 4-bit) for GPU efficiency.
- Explicit `classifier_params` dictionary override for custom calibrated pairs.
- Configurable `max_token_observed` (defaulting to tokenizer's model_max_length).
- `score_window` convenience method for window-level pipeline integration.

Edge behaviour intentionally matches upstream:
- Empty string raises RuntimeError from model forward pass.
- 1-token input returns nan criterion.
- Batch > 1 raises AssertionError.
- Length (<150 words) and language guardrails belong to caller/ensemble layer.
"""

from __future__ import annotations

import os
from typing import Any

import numpy as np
import torch
import transformers
from scipy.stats import norm
from transformers import AutoModelForCausalLM, AutoTokenizer

DISTRIB_PARAMS: dict[str, dict[str, float]] = {
    "gpt-j-6B_gpt-neo-2.7B": {
        "mu0": 0.2713,
        "sigma0": 0.9366,
        "mu1": 2.2334,
        "sigma1": 1.8731,
    },
    "gpt-neo-2.7B_gpt-neo-2.7B": {
        "mu0": -0.2489,
        "sigma0": 0.9968,
        "mu1": 1.8983,
        "sigma1": 1.9935,
    },
    "falcon-7b_falcon-7b-instruct": {
        "mu0": -0.0707,
        "sigma0": 0.9520,
        "mu1": 2.9306,
        "sigma1": 1.9039,
    },
    "llama3-8b_llama3-8b-instruct": {
        "mu0": 0.1603,
        "sigma0": 1.0791,
        "mu1": 2.4686,
        "sigma1": 2.1582,
    },
}

DEFAULT_SAMPLING_MODEL = "falcon-7b"
DEFAULT_SCORING_MODEL = "falcon-7b-instruct"

# Predefined model alias mapping matching upstream scripts/model.py:19-34
MODEL_ALIASES: dict[str, str] = {
    "gpt2": "gpt2",
    "gpt2-xl": "gpt2-xl",
    "opt-2.7b": "facebook/opt-2.7b",
    "gpt-neo-2.7B": "EleutherAI/gpt-neo-2.7B",
    "gpt-j-6B": "EleutherAI/gpt-j-6B",
    "gpt-neox-20b": "EleutherAI/gpt-neox-20b",
    "mgpt": "sberbank-ai/mGPT",
    "pubmedgpt": "stanford-crfm/pubmedgpt",
    "mt5-xl": "google/mt5-xl",
    "llama-13b": "huggyllama/llama-13b",
    "llama2-13b": "TheBloke/Llama-2-13B-fp16",
    "bloom-7b1": "bigscience/bloom-7b1",
    "opt-13b": "facebook/opt-13b",
    "falcon-7b": "tiiuae/falcon-7b",
    "falcon-7b-instruct": "tiiuae/falcon-7b-instruct",
}

FLOAT16_MODELS: list[str] = [
    "gpt-neo-2.7B",
    "gpt-j-6B",
    "gpt-neox-20b",
    "llama-13b",
    "llama2-13b",
    "bloom-7b1",
    "opt-13b",
    "falcon-7b",
    "falcon-7b-instruct",
]


def resolve_model_name(name: str) -> str:
    return MODEL_ALIASES.get(name, name)


def compute_prob_norm(
    x: float, mu0: float, sigma0: float, mu1: float, sigma1: float
) -> float:
    """Balanced-prior two-Normal Bayes probability that text is machine-generated."""
    pdf0 = float(norm.pdf(x, loc=mu0, scale=sigma0))
    pdf1 = float(norm.pdf(x, loc=mu1, scale=sigma1))
    denom = pdf0 + pdf1
    if denom == 0.0:
        return 0.5
    return float(pdf1 / denom)


def compute_discrepancy_analytic(
    logits_ref: torch.Tensor,
    logits_score: torch.Tensor,
    labels: torch.Tensor,
) -> float:
    """Computes Fast-DetectGPT analytic conditional probability curvature.

    Rebuilt from baoguangsheng/fast-detect-gpt scripts/fast_detect_gpt.py:52-70.
    """
    assert logits_ref.shape[0] == 1, "Only batch size 1 is supported"
    assert logits_score.shape[0] == 1, "Only batch size 1 is supported"
    assert labels.shape[0] == 1, "Only batch size 1 is supported"

    # Edge case: if labels has 0 elements (1-token input where [:, 1:] is empty)
    if labels.size(1) == 0:
        return float("nan")

    # Vocab size alignment if mismatched
    if logits_ref.size(-1) != logits_score.size(-1):
        min_v = min(logits_ref.size(-1), logits_score.size(-1))
        logits_ref = logits_ref[:, :, :min_v]
        logits_score = logits_score[:, :, :min_v]

    if labels.ndim == logits_score.ndim - 1:
        labels = labels.unsqueeze(-1)

    lprobs_score = torch.log_softmax(logits_score, dim=-1)
    probs_ref = torch.softmax(logits_ref, dim=-1)

    # Log likelihood of the ground truth next token under scoring model
    log_likelihood = lprobs_score.gather(dim=-1, index=labels).squeeze(-1)

    # Expectation and variance under reference sampling distribution
    mean_ref = (probs_ref * lprobs_score).sum(dim=-1)
    var_ref = (probs_ref * torch.square(lprobs_score)).sum(dim=-1) - torch.square(mean_ref)

    sum_var = var_ref.sum(dim=-1)
    if sum_var <= 0:
        return float("nan")

    discrepancy = (log_likelihood.sum(dim=-1) - mean_ref.sum(dim=-1)) / sum_var.sqrt()
    return float(discrepancy.mean().item())


class FastDetectGPTDetector:
    def __init__(
        self,
        sampling_model_name: str = DEFAULT_SAMPLING_MODEL,
        scoring_model_name: str = DEFAULT_SCORING_MODEL,
        device: str | None = None,
        use_float16: bool | None = None,
        max_token_observed: int | None = None,
        quantize: str | None = None,
        classifier_params: dict[str, float] | None = None,
    ) -> None:
        if quantize not in (None, "8bit", "4bit"):
            raise ValueError(f"Invalid quantize option: {quantize!r} (use None, '8bit' or '4bit')")

        self.sampling_model_name = sampling_model_name
        self.scoring_model_name = scoring_model_name
        self.max_token_observed = max_token_observed
        self.device = device or ("cuda:0" if torch.cuda.is_available() else "cpu")

        # Load scoring tokenizer
        scoring_full = resolve_model_name(scoring_model_name)
        tok_kwargs: dict[str, Any] = {"padding_side": "right"}
        if "facebook/opt-" in scoring_full:
            tok_kwargs["fast"] = False
        self.scoring_tokenizer = AutoTokenizer.from_pretrained(scoring_full, **tok_kwargs)
        if self.scoring_tokenizer.pad_token_id is None:
            if "13b" in scoring_full:
                self.scoring_tokenizer.pad_token_id = 0
            else:
                self.scoring_tokenizer.pad_token_id = self.scoring_tokenizer.eos_token_id

        # Load scoring model
        self.scoring_model = self._load_causal_lm(scoring_model_name, use_float16, quantize)

        # Load sampling model if different
        if sampling_model_name != scoring_model_name:
            sampling_full = resolve_model_name(sampling_model_name)
            s_tok_kwargs: dict[str, Any] = {"padding_side": "right"}
            if "facebook/opt-" in sampling_full:
                s_tok_kwargs["fast"] = False
            self.sampling_tokenizer = AutoTokenizer.from_pretrained(sampling_full, **s_tok_kwargs)
            if self.sampling_tokenizer.pad_token_id is None:
                if "13b" in sampling_full:
                    self.sampling_tokenizer.pad_token_id = 0
                else:
                    self.sampling_tokenizer.pad_token_id = self.sampling_tokenizer.eos_token_id
            self.sampling_model = self._load_causal_lm(sampling_model_name, use_float16, quantize)
        else:
            self.sampling_tokenizer = self.scoring_tokenizer
            self.sampling_model = self.scoring_model

        # Distribution parameter setup (matching upstream local_infer.py:51-52 failure order)
        if classifier_params is not None:
            self.classifier = classifier_params
        else:
            key = f"{sampling_model_name}_{scoring_model_name}"
            if key not in DISTRIB_PARAMS:
                raise KeyError(
                    f"Unknown model pair '{key}' for FastDetectGPT. Published pairs: "
                    f"{list(DISTRIB_PARAMS.keys())}. Provide classifier_params to override."
                )
            self.classifier = DISTRIB_PARAMS[key]

    def _load_causal_lm(
        self,
        model_name: str,
        use_float16: bool | None,
        quantize: str | None,
    ) -> AutoModelForCausalLM:
        fullname = resolve_model_name(model_name)
        load_kwargs: dict[str, Any] = {"trust_remote_code": True}

        # Determine dtype
        if use_float16 is not None:
            dtype = torch.float16 if use_float16 else torch.float32
        else:
            dtype = torch.float16 if model_name in FLOAT16_MODELS else torch.float32

        if self.device.startswith("cpu") and dtype == torch.float16:
            dtype = torch.float32

        major = int(transformers.__version__.split(".")[0])
        load_kwargs["dtype" if major >= 5 else "torch_dtype"] = dtype

        if "gpt-j" in model_name:
            load_kwargs["revision"] = "float16"

        if quantize is not None:
            from transformers import BitsAndBytesConfig

            load_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_8bit=quantize == "8bit",
                load_in_4bit=quantize == "4bit",
            )

        model = AutoModelForCausalLM.from_pretrained(fullname, **load_kwargs)
        if quantize is None:
            model = model.to(self.device)
        model.eval()
        return model

    def _tokenize(self, text: str, tokenizer: AutoTokenizer) -> transformers.BatchEncoding:
        tok_kwargs: dict[str, Any] = {
            "truncation": True,
            "return_tensors": "pt",
            "padding": True,
            "return_token_type_ids": False,
        }
        if self.max_token_observed is not None:
            tok_kwargs["max_length"] = self.max_token_observed
        return tokenizer(text, **tok_kwargs).to(self.device)

    def compute_crit(self, text: str) -> tuple[float, int]:
        """Compute the analytic curvature criterion.

        Returns:
            (criterion, ntoken) where ntoken = labels.size(1) = n_tokens - 1.
        """
        if not isinstance(text, str):
            raise TypeError(f"Expected str, got {type(text)}")

        tokenized = self._tokenize(text, self.scoring_tokenizer)
        labels = tokenized.input_ids[:, 1:]

        # Upstream edge case: empty input string causes RuntimeError on forward pass
        with torch.no_grad():
            logits_score = self.scoring_model(**tokenized).logits[:, :-1]
            if self.sampling_model_name == self.scoring_model_name:
                logits_ref = logits_score
            else:
                tokenized_ref = self._tokenize(text, self.sampling_tokenizer)
                assert torch.all(tokenized_ref.input_ids[:, 1:] == labels), "Tokenizer is mismatch."
                logits_ref = self.sampling_model(**tokenized_ref).logits[:, :-1]

            crit = compute_discrepancy_analytic(logits_ref, logits_score, labels)
        return crit, labels.size(1)

    def compute_prob(self, text: str) -> tuple[float, float, int]:
        """Compute the machine-generated probability and raw criterion.

        Returns:
            (probability, criterion, ntoken)
        """
        crit, ntoken = self.compute_crit(text)
        prob = compute_prob_norm(
            crit,
            mu0=self.classifier["mu0"],
            sigma0=self.classifier["sigma0"],
            mu1=self.classifier["mu1"],
            sigma1=self.classifier["sigma1"],
        )
        return prob, crit, ntoken

    def score_window(self, text: str) -> dict[str, Any]:
        """Project-side helper for window-level analysis."""
        prob, crit, ntoken = self.compute_prob(text)
        return {
            "criterion": crit,
            "probability": prob,
            "n_tokens": ntoken + 1,
        }
