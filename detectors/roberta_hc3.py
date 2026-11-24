"""RoBERTa HC3 AI Detector Rebuild (Step 12, Repo #6).

Clean in-tree implementation of Hello-SimpleAI/chatgpt-detector-roberta sequence
classification. Evaluates single-window or document passages up to 512 tokens
and outputs calibrated softmax probability for the ChatGPT/AI class.

Features:
  1. Direct HuggingFace Transformers sequence classification.
  2. Sub-second CPU inference using PyTorch float32.
  3. Offline heuristic fallback when checkpoint weights are not present.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import torch
import torch.nn.functional as F
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "Hello-SimpleAI/chatgpt-detector-roberta"


class RobertaHC3Detector:
    def __init__(
        self,
        model_name_or_path: str = DEFAULT_MODEL_NAME,
        device: str = "cpu",
        lazy_load: bool = True,
        force_fallback: bool = False,
    ) -> None:
        self.model_name_or_path = model_name_or_path
        self.device = device
        self.force_fallback = force_fallback or os.environ.get("ROBERTA_OFFLINE_TEST") == "1"
        self._tokenizer = None
        self._model = None
        self._is_available = not self.force_fallback

        if not lazy_load and not self.force_fallback:
            self._load_model()

    def _load_model(self) -> None:
        if self._model is not None or self.force_fallback:
            return

        try:
            # Try loading with local_files_only first to avoid network stall
            try:
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_name_or_path, local_files_only=True)
                self._model = AutoModelForSequenceClassification.from_pretrained(
                    self.model_name_or_path, local_files_only=True
                )
            except Exception:
                # If not cached locally, attempt online load with timeout
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_name_or_path)
                self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name_or_path)

            self._model.to(self.device)
            self._model.eval()
            self._is_available = True
        except Exception as exc:
            logger.warning(
                "Unable to load RoBERTa HC3 weights from %s: %s. Using heuristic scoring fallback.",
                self.model_name_or_path,
                exc,
            )
            self._is_available = False

    @property
    def is_available(self) -> bool:
        if self._model is None and self._is_available:
            self._load_model()
        return self._is_available

    def score_text(self, text: str) -> dict[str, Any]:
        """Score a text passage (up to 512 tokens).

        Returns:
            dict containing:
              - ai_probability (0.0 to 1.0)
              - human_probability (0.0 to 1.0)
              - predicted_label ("ai" | "human")
              - model: str
        """
        if not text or not text.strip():
            return {
                "ai_probability": 0.0,
                "human_probability": 1.0,
                "predicted_label": "human",
                "model": "roberta_hc3_fallback",
            }

        self._load_model()

        if not self._is_available or self._model is None or self._tokenizer is None:
            # Fallback estimation based on lexical perplexity indicators
            lower_text = text.lower()
            ai_indicators = ["furthermore", "moreover", "in conclusion", "it is important to note", "crucial", "delve"]
            matches = sum(1 for ind in ai_indicators if ind in lower_text)
            prob = min(0.95, max(0.05, matches * 0.20 + 0.15))
            return {
                "ai_probability": prob,
                "human_probability": 1.0 - prob,
                "predicted_label": "ai" if prob >= 0.50 else "human",
                "model": "roberta_hc3_heuristic_fallback",
            }

        inputs = self._tokenizer(
            text,
            max_length=512,
            truncation=True,
            padding=False,
            return_tensors="pt",
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)
            logits = outputs.logits
            probs = F.softmax(logits, dim=-1)[0]

            # Label 0: Human, Label 1: ChatGPT / AI
            human_prob = float(probs[0].item())
            ai_prob = float(probs[1].item()) if probs.shape[0] > 1 else (1.0 - human_prob)

        return {
            "ai_probability": ai_prob,
            "human_probability": human_prob,
            "predicted_label": "ai" if ai_prob >= 0.50 else "human",
            "model": self.model_name_or_path,
        }
