"""2-Signal AI Detection Ensemble & Calibration Guardrails (Step 7).

Combines Binoculars and Fast-DetectGPT scores using a calibrated logistic
regression model, attaches GLTR forensic token-rank details to AI-flagged
windows, and rolls up window-level probabilities to Document AI %.

Enforces production guardrails:
  1. Length guardrail: skips documents with < 150 words ("Too short to estimate").
  2. Language guardrail: flags non-English text with a confidence warning.
  3. Ethical disclaimer: "Estimate only, not proof".
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from detectors.binoculars import BinocularsDetector
from detectors.fastdetect import FastDetectGPTDetector
from detectors.gltr_ranks import GLTRRankDetector, GLTRReport
from detectors.roberta_hc3 import RobertaHC3Detector
from ingest.chunker import Window, chunk, split_sentences

WORD_RE = re.compile(r"\b\S+\b")
LATIN_RE = re.compile(r"[A-Za-z]")

# Default calibrated parameters (from scripts/calibrate.py)
DEFAULT_CALIBRATION_PATH = Path(__file__).parent / "calibration_params.json"
DEFAULT_INTERCEPT = 0.3714
DEFAULT_WEIGHT_BINO = -0.0764
DEFAULT_WEIGHT_FD = 0.3604
DEFAULT_THRESHOLD = 0.50

DISCLAIMER_TEXT = "Estimate only, not proof. AI detection scores represent probabilistic estimates and must be verified by human review."


def is_non_english(text: str, non_ascii_ratio_threshold: float = 0.20) -> bool:
    """Detect if text is primarily non-English using character script distribution."""
    clean_chars = [ch for ch in text if ch.isalpha()]
    if not clean_chars:
        return False
    latin_chars = sum(1 for ch in clean_chars if LATIN_RE.match(ch))
    latin_ratio = latin_chars / len(clean_chars)
    return latin_ratio < (1.0 - non_ascii_ratio_threshold)


def sigmoid(z: float) -> float:
    """Standard numerically stable logistic sigmoid."""
    if z >= 0:
        return float(1.0 / (1.0 + math.exp(-z)))
    else:
        ez = math.exp(z)
        return float(ez / (1.0 + ez))


@dataclass
class WindowPrediction:
    window_idx: int
    text: str
    start_char: int
    end_char: int
    n_words: int
    fused_probability: float
    is_ai: bool
    binoculars_score: float
    fastdetect_criterion: float
    fastdetect_probability: float
    gltr_forensics: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_idx": self.window_idx,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "n_words": self.n_words,
            "fused_probability": round(self.fused_probability, 4),
            "is_ai": self.is_ai,
            "binoculars_score": round(self.binoculars_score, 4),
            "fastdetect_criterion": round(self.fastdetect_criterion, 4),
            "fastdetect_probability": round(self.fastdetect_probability, 4),
            "gltr_forensics": self.gltr_forensics,
        }


@dataclass
class DocumentPrediction:
    status: str  # "DONE" | "TOO_SHORT"
    message: str
    document_ai_pct: float | None
    total_words: int
    flagged_ai_words: int
    qualitative_label: str  # "Likely human-generated" | "Mixed / partially AI-generated" | "Likely AI-generated" | "Too short to estimate"
    disclaimer: str
    is_english: bool
    confidence_warning: str | None
    windows: list[WindowPrediction] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "document_ai_pct": round(self.document_ai_pct, 2) if self.document_ai_pct is not None else None,
            "total_words": self.total_words,
            "flagged_ai_words": self.flagged_ai_words,
            "qualitative_label": self.qualitative_label,
            "disclaimer": self.disclaimer,
            "is_english": self.is_english,
            "confidence_warning": self.confidence_warning,
            "windows": [w.to_dict() for w in self.windows],
        }


class AIEnsembleDetector:
    def __init__(
        self,
        binoculars: BinocularsDetector | None = None,
        fastdetect: FastDetectGPTDetector | None = None,
        gltr: GLTRRankDetector | None = None,
        roberta: RobertaHC3Detector | None = None,
        calibration_path: str | Path | None = DEFAULT_CALIBRATION_PATH,
        threshold: float | None = None,
        enable_roberta: bool = False,
        device: str | None = None,
    ) -> None:
        self.device = device or "cpu"
        self.enable_roberta = enable_roberta

        # Load calibrated coefficients
        self.intercept = DEFAULT_INTERCEPT
        self.weight_bino = DEFAULT_WEIGHT_BINO
        self.weight_fd = DEFAULT_WEIGHT_FD
        self.threshold = threshold or DEFAULT_THRESHOLD

        if calibration_path and os.path.exists(calibration_path):
            try:
                with open(calibration_path, "r", encoding="utf-8") as f:
                    params = json.load(f)
                    self.intercept = params.get("intercept", self.intercept)
                    self.weight_bino = params.get("weight_binoculars", self.weight_bino)
                    self.weight_fd = params.get("weight_fastdetect", self.weight_fd)
                    if threshold is None:
                        self.threshold = params.get("operating_threshold", self.threshold)
            except Exception:
                pass

        # Detectors (injected or lazy loaded)
        self._binoculars = binoculars
        self._fastdetect = fastdetect
        self._gltr = gltr
        self._roberta = roberta

    @property
    def roberta(self) -> RobertaHC3Detector:
        if self._roberta is None:
            self._roberta = RobertaHC3Detector(device=self.device)
        return self._roberta

    @property
    def binoculars(self) -> BinocularsDetector:
        if self._binoculars is None:
            self._binoculars = BinocularsDetector(
                observer_name_or_path="gpt2",
                performer_name_or_path="distilgpt2",
                use_bfloat16=False,
            )
        return self._binoculars

    @property
    def fastdetect(self) -> FastDetectGPTDetector:
        if self._fastdetect is None:
            from detectors.fastdetect import DISTRIB_PARAMS

            falcon_params = DISTRIB_PARAMS["falcon-7b_falcon-7b-instruct"]
            self._fastdetect = FastDetectGPTDetector(
                sampling_model_name="gpt2",
                scoring_model_name="gpt2",
                device="cpu",
                use_float16=False,
                classifier_params=falcon_params,
            )
        return self._fastdetect

    @property
    def gltr(self) -> GLTRRankDetector:
        if self._gltr is None:
            self._gltr = GLTRRankDetector(model_name="gpt2", device="cpu")
        return self._gltr

    def predict_window(
        self,
        text: str,
        window_idx: int = 0,
        start_char: int = 0,
        end_char: int = 0,
    ) -> WindowPrediction:
        """Run 2-signal fusion on a single window of text."""
        w_bino = self.binoculars.score_window(text)
        w_fd = self.fastdetect.score_window(text)

        bino_score = w_bino["score"]
        fd_crit = w_fd["criterion"]
        fd_prob = w_fd["probability"]

        # 2-signal logistic regression logit
        z = self.intercept + (self.weight_bino * bino_score) + (self.weight_fd * fd_crit)

        # 3-signal upgrade when RoBERTa is enabled
        if self.enable_roberta:
            try:
                r_res = self.roberta.score_text(text)
                r_prob = r_res["ai_probability"]
                # Integrate RoBERTa probability centered around 0.5
                z += 1.2 * (r_prob - 0.5)
            except Exception:
                pass

        fused_prob = sigmoid(z)
        is_ai = fused_prob >= self.threshold

        gltr_forensics = None
        if is_ai:
            # Attach GLTR token ranks for forensic detail view
            gltr_report = self.gltr.analyze_text(text)
            gltr_forensics = gltr_report.to_dict()

        words = WORD_RE.findall(text)
        return WindowPrediction(
            window_idx=window_idx,
            text=text,
            start_char=start_char,
            end_char=end_char if end_char > 0 else len(text),
            n_words=len(words),
            fused_probability=fused_prob,
            is_ai=is_ai,
            binoculars_score=bino_score,
            fastdetect_criterion=fd_crit,
            fastdetect_probability=fd_prob,
            gltr_forensics=gltr_forensics,
        )

    def predict_document(self, text: str, max_windows: int | None = 4) -> DocumentPrediction:
        """Score an entire document with length & language guardrails."""
        words = list(WORD_RE.finditer(text))
        total_words = len(words)

        # 1. Guardrail: Length check (< 150 words skip)
        if total_words < 150:
            return DocumentPrediction(
                status="TOO_SHORT",
                message="Too short to estimate",
                document_ai_pct=None,
                total_words=total_words,
                flagged_ai_words=0,
                qualitative_label="Too short to estimate",
                disclaimer=DISCLAIMER_TEXT,
                is_english=True,
                confidence_warning=None,
                windows=[],
            )

        # 2. Guardrail: Non-English language check
        non_english = is_non_english(text)
        confidence_warning = (
            "Text appears to be in a non-English language. AI detection confidence may be reduced."
            if non_english
            else None
        )

        # 3. Chunk into ~250-word sliding windows (50% overlap)
        doc_windows = chunk(text, window_words=250, overlap=0.5)
        if not doc_windows:
            # Fallback for text >= 150 words without sentence boundaries
            doc_windows = [
                Window(
                    text=text,
                    start_char=0,
                    end_char=len(text),
                    n_words=total_words,
                    first_sentence=0,
                    last_sentence=0,
                )
            ]
        elif max_windows is not None and len(doc_windows) > max_windows:
            # For long documents on CPU, sample windows uniformly across intro, body, and conclusion
            step = (len(doc_windows) - 1) / (max_windows - 1) if max_windows > 1 else len(doc_windows)
            indices = sorted(list({round(i * step) for i in range(max_windows)}))
            doc_windows = [doc_windows[i] for i in indices]

        # 4. Score each window
        predictions: list[WindowPrediction] = []
        for idx, w in enumerate(doc_windows):
            pred = self.predict_window(
                text=w.text,
                window_idx=idx,
                start_char=w.start_char,
                end_char=w.end_char,
            )
            predictions.append(pred)

        # 5. Window-to-document word-level rollup
        # A word is counted as AI if it falls inside any AI-flagged window
        word_is_ai = [False] * total_words
        for pred in predictions:
            if pred.is_ai:
                for w_idx, w_match in enumerate(words):
                    if w_match.start() >= pred.start_char and w_match.end() <= pred.end_char:
                        word_is_ai[w_idx] = True

        flagged_words = sum(1 for flagged in word_is_ai if flagged)
        document_ai_pct = (flagged_words / total_words) * 100.0

        # Qualitative label
        if document_ai_pct <= 15.0:
            label = "Likely human-generated"
        elif document_ai_pct <= 50.0:
            label = "Mixed / partially AI-generated"
        else:
            label = "Likely AI-generated"

        return DocumentPrediction(
            status="DONE",
            message="Analysis complete",
            document_ai_pct=document_ai_pct,
            total_words=total_words,
            flagged_ai_words=flagged_words,
            qualitative_label=label,
            disclaimer=DISCLAIMER_TEXT,
            is_english=not non_english,
            confidence_warning=confidence_warning,
            windows=predictions,
        )
