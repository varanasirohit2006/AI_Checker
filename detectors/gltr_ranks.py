"""GLTR Token-Rank Forensic Analyzer (Repo #3).

Rebuilt from HendrikStrobelt/detecting-fake-text (GLTR, Apache-2.0).
Computes per-token predictive rank under a causal language model
(e.g., GPT-2), categorizing tokens into forensic color buckets:
  * Rank <= 10:   Top-10 (Green)   — highly predictable / typical of AI
  * Rank <= 100:  Top-100 (Yellow) — predictable
  * Rank <= 1000: Top-1000 (Red)   — moderate surprise
  * Rank > 1000:  Rest (Purple)    — high human surprise / creative choice
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

DEFAULT_GLTR_MODEL = "gpt2"


@dataclass
class TokenRank:
    token: str
    token_id: int
    rank: int
    bucket: str  # "top-10" | "top-100" | "top-1000" | "rest"
    color: str   # "green" | "yellow" | "red" | "purple"


@dataclass
class GLTRReport:
    total_tokens: int
    top10_count: int
    top100_count: int
    top1000_count: int
    rest_count: int
    top10_pct: float
    top100_pct: float
    top1000_pct: float
    rest_pct: float
    token_ranks: list[TokenRank]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_tokens": self.total_tokens,
            "top10_pct": round(self.top10_pct, 2),
            "top100_pct": round(self.top100_pct, 2),
            "top1000_pct": round(self.top1000_pct, 2),
            "rest_pct": round(self.rest_pct, 2),
            "token_ranks": [
                {
                    "token": tr.token,
                    "rank": tr.rank,
                    "bucket": tr.bucket,
                    "color": tr.color,
                }
                for tr in self.token_ranks
            ],
        }


def assign_bucket(rank: int) -> tuple[str, str]:
    """Map a 1-indexed token rank to GLTR bucket and UI color."""
    if rank <= 10:
        return "top-10", "green"
    elif rank <= 100:
        return "top-100", "yellow"
    elif rank <= 1000:
        return "top-1000", "red"
    else:
        return "rest", "purple"


class GLTRRankDetector:
    def __init__(
        self,
        model_name: str = DEFAULT_GLTR_MODEL,
        device: str | None = None,
        model: AutoModelForCausalLM | None = None,
        tokenizer: AutoTokenizer | None = None,
    ) -> None:
        self.device = device or ("cuda:0" if torch.cuda.is_available() else "cpu")
        self.model_name = model_name

        if tokenizer is not None:
            self.tokenizer = tokenizer
        else:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

        if model is not None:
            self.model = model
        else:
            self.model = AutoModelForCausalLM.from_pretrained(model_name).to(self.device)
        self.model.eval()

    def analyze_text(self, text: str, max_tokens: int = 512) -> GLTRReport:
        """Compute GLTR token ranks for text."""
        encodings = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=max_tokens,
            return_token_type_ids=False,
        ).to(self.device)

        input_ids = encodings.input_ids
        n_tokens = input_ids.shape[1]

        if n_tokens <= 1:
            return GLTRReport(
                total_tokens=n_tokens,
                top10_count=0,
                top100_count=0,
                top1000_count=0,
                rest_count=0,
                top10_pct=0.0,
                top100_pct=0.0,
                top1000_pct=0.0,
                rest_pct=0.0,
                token_ranks=[],
            )

        with torch.no_grad():
            logits = self.model(**encodings).logits[:, :-1, :]  # (1, T-1, V)
            targets = input_ids[:, 1:]                           # (1, T-1)

        token_ranks: list[TokenRank] = []
        counts = {"top-10": 0, "top-100": 0, "top-1000": 0, "rest": 0}

        # Calculate rank per token: rank = (logits > target_logit).sum() + 1
        for pos in range(targets.shape[1]):
            target_id = targets[0, pos].item()
            pos_logits = logits[0, pos]
            target_logit = pos_logits[target_id].item()

            # Rank is number of vocabulary items with strictly higher logit + 1
            rank = int((pos_logits > target_logit).sum().item()) + 1
            bucket, color = assign_bucket(rank)
            counts[bucket] += 1

            token_str = self.tokenizer.decode([target_id])
            token_ranks.append(
                TokenRank(
                    token=token_str,
                    token_id=target_id,
                    rank=rank,
                    bucket=bucket,
                    color=color,
                )
            )

        evaluated_tokens = len(token_ranks)
        top10_pct = (counts["top-10"] / evaluated_tokens) * 100.0
        top100_pct = (counts["top-100"] / evaluated_tokens) * 100.0
        top1000_pct = (counts["top-1000"] / evaluated_tokens) * 100.0
        rest_pct = (counts["rest"] / evaluated_tokens) * 100.0

        return GLTRReport(
            total_tokens=evaluated_tokens,
            top10_count=counts["top-10"],
            top100_count=counts["top-100"],
            top1000_count=counts["top-1000"],
            rest_count=counts["rest"],
            top10_pct=top10_pct,
            top100_pct=top100_pct,
            top1000_pct=top1000_pct,
            rest_pct=rest_pct,
            token_ranks=token_ranks,
        )
