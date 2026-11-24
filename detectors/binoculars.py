"""Binoculars AI-text detector — clean REA rebuild of ahans30/Binoculars.

Upstream: https://github.com/ahans30/Binoculars (BSD-3-Clause, commit
c8ae2f90d50ee696418bc71d8d9e5020e5f9d7b8). Full license text and attribution
are recorded in THIRD_PARTY_LICENSES.md. Behaviour rebuilt from
rea/binoculars/04-spec.md; no upstream code copied.

Score = mean performer cross-entropy (nats, NOT exponentiated) divided by the
mean cross-entropy of the observer's softmax distribution against the
performer logits. Lower score => more likely AI-generated.

Extensions beyond upstream (NOT covered by the differential test):
per-model device overrides and optional bitsandbytes 8-bit/4-bit quantization.
Scores produced with quantized weights will differ from upstream fp32/bf16
numbers. The published thresholds were tuned on Falcon-7B/Falcon-7B-Instruct
in bfloat16 and need re-calibration for other model pairs.

Edge behaviour intentionally matches upstream: empty input raises
RuntimeError; single-token input yields nan. Length/language guardrails belong
to the caller layer, not this module.
"""

from __future__ import annotations

import os

import torch
import transformers
from transformers import AutoModelForCausalLM, AutoTokenizer

BINOCULARS_ACCURACY_THRESHOLD = 0.9015310749276843
BINOCULARS_FPR_THRESHOLD = 0.8536432310785527
DEFAULT_OBSERVER = "tiiuae/falcon-7b"
DEFAULT_PERFORMER = "tiiuae/falcon-7b-instruct"
DEFAULT_MAX_TOKEN_OBSERVED = 512

_LABEL_AI = "Most likely AI-generated"
_LABEL_HUMAN = "Most likely human-generated"


def _default_device() -> str:
    return "cuda:0" if torch.cuda.is_available() else "cpu"


def _dtype_kwarg(dtype: torch.dtype) -> dict:
    # transformers >= 5 renamed torch_dtype -> dtype in from_pretrained.
    major = int(transformers.__version__.split(".")[0])
    return {"dtype" if major >= 5 else "torch_dtype": dtype}


def _require_matching_vocabs(observer_id: str, performer_id: str) -> None:
    observer_vocab = AutoTokenizer.from_pretrained(observer_id).vocab
    performer_vocab = AutoTokenizer.from_pretrained(performer_id).vocab
    if observer_vocab != performer_vocab:
        raise ValueError(
            f"Tokenizers are not identical for {observer_id} and {performer_id}."
        )


def _performer_mean_ce(
    logits: torch.Tensor,
    input_ids: torch.Tensor,
    attention_mask: torch.Tensor,
) -> torch.Tensor:
    """Numerator: mean next-token CE of the performer, in nats (no exp)."""
    next_token_logits = logits[:, :-1, :]
    next_token_ids = input_ids[:, 1:]
    next_token_mask = attention_mask[:, 1:]
    ce = torch.nn.functional.cross_entropy(
        next_token_logits.transpose(1, 2), next_token_ids, reduction="none"
    )
    return (ce * next_token_mask).sum(dim=1) / next_token_mask.sum(dim=1)


def _observer_performer_cross_ce(
    observer_logits: torch.Tensor,
    performer_logits: torch.Tensor,
    input_ids: torch.Tensor,
    pad_token_id: int,
) -> torch.Tensor:
    """Denominator: mean CE of observer softmax (soft targets) under performer."""
    vocab_size = observer_logits.shape[-1]
    seq_len = performer_logits.shape[-2]
    soft_targets = torch.softmax(observer_logits, dim=-1).view(-1, vocab_size)
    ce = torch.nn.functional.cross_entropy(
        performer_logits.view(-1, vocab_size), soft_targets, reduction="none"
    ).view(-1, seq_len)
    non_pad_mask = (input_ids != pad_token_id).to(torch.uint8)
    return (ce * non_pad_mask).sum(dim=1) / non_pad_mask.sum(dim=1)


class BinocularsDetector:
    def __init__(
        self,
        observer_name_or_path: str = DEFAULT_OBSERVER,
        performer_name_or_path: str = DEFAULT_PERFORMER,
        use_bfloat16: bool = True,
        max_token_observed: int = DEFAULT_MAX_TOKEN_OBSERVED,
        mode: str = "low-fpr",
        device_observer: str | None = None,
        device_performer: str | None = None,
        quantize: str | None = None,
    ) -> None:
        if quantize not in (None, "8bit", "4bit"):
            raise ValueError(f"Invalid quantize option: {quantize!r} (use None, '8bit' or '4bit')")
        self.change_mode(mode)
        _require_matching_vocabs(observer_name_or_path, performer_name_or_path)

        base_device = _default_device()
        self.device_observer = device_observer or base_device
        self.device_performer = device_performer or base_device
        if use_bfloat16 and (
            self.device_observer.startswith("cpu") or self.device_performer.startswith("cpu")
        ):
            raise ValueError(
                "bfloat16 is not supported on CPU for this detector; pass use_bfloat16=False."
            )
        dtype = torch.bfloat16 if use_bfloat16 else torch.float32

        load_kwargs: dict = {
            "trust_remote_code": True,
            "token": os.environ.get("HF_TOKEN", None),
            **_dtype_kwarg(dtype),
        }
        if quantize is not None:
            from transformers import BitsAndBytesConfig

            load_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_8bit=quantize == "8bit",
                load_in_4bit=quantize == "4bit",
            )

        self.observer_model = AutoModelForCausalLM.from_pretrained(
            observer_name_or_path, device_map={"": self.device_observer}, **load_kwargs
        )
        self.performer_model = AutoModelForCausalLM.from_pretrained(
            performer_name_or_path, device_map={"": self.device_performer}, **load_kwargs
        )
        self.observer_model.eval()
        self.performer_model.eval()

        self.tokenizer = AutoTokenizer.from_pretrained(observer_name_or_path)
        if not self.tokenizer.pad_token:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.max_token_observed = max_token_observed

    def change_mode(self, mode: str) -> None:
        if mode == "low-fpr":
            self.threshold = BINOCULARS_FPR_THRESHOLD
        elif mode == "accuracy":
            self.threshold = BINOCULARS_ACCURACY_THRESHOLD
        else:
            raise ValueError(f"Invalid mode: {mode}")

    def _tokenize(self, batch: list[str]) -> transformers.BatchEncoding:
        return self.tokenizer(
            batch,
            return_tensors="pt",
            padding="longest" if len(batch) > 1 else False,
            truncation=True,
            max_length=self.max_token_observed,
            return_token_type_ids=False,
        ).to(self.device_observer)

    @torch.inference_mode()
    def _forward(self, encodings: transformers.BatchEncoding) -> tuple[torch.Tensor, torch.Tensor]:
        observer_logits = self.observer_model(
            **encodings.to(self.device_observer)
        ).logits
        performer_logits = self.performer_model(
            **encodings.to(self.device_performer)
        ).logits
        if not self.device_observer.startswith("cpu"):
            torch.cuda.synchronize()
        return observer_logits, performer_logits

    def _score_components(
        self, encodings: transformers.BatchEncoding
    ) -> tuple[torch.Tensor, torch.Tensor]:
        observer_logits, performer_logits = self._forward(encodings)
        ppl = _performer_mean_ce(
            performer_logits, encodings.input_ids, encodings.attention_mask
        )
        x_ppl = _observer_performer_cross_ce(
            observer_logits.to(self.device_observer),
            performer_logits.to(self.device_observer),
            encodings.input_ids.to(self.device_observer),
            self.tokenizer.pad_token_id,
        )
        return ppl.float().cpu(), x_ppl.float().cpu()

    def compute_score(self, input_text: str | list[str]) -> float | list[float]:
        batch = [input_text] if isinstance(input_text, str) else input_text
        encodings = self._tokenize(batch)
        ppl, x_ppl = self._score_components(encodings)
        scores = (ppl / x_ppl).tolist()
        return scores[0] if isinstance(input_text, str) else scores

    def predict(self, input_text: str | list[str]) -> str | list[str]:
        scores = self.compute_score(input_text)
        if isinstance(input_text, str):
            return _LABEL_AI if scores < self.threshold else _LABEL_HUMAN
        return [_LABEL_AI if s < self.threshold else _LABEL_HUMAN for s in scores]

    def score_window(self, text: str) -> dict:
        """Project-side convenience: score plus its components for one window."""
        encodings = self._tokenize([text])
        ppl, x_ppl = self._score_components(encodings)
        score = float((ppl / x_ppl)[0])
        return {
            "score": score,
            "label": _LABEL_AI if score < self.threshold else _LABEL_HUMAN,
            "ppl": float(ppl[0]),
            "x_ppl": float(x_ppl[0]),
            "n_tokens": int(encodings.input_ids.shape[-1]),
        }