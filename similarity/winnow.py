"""Winnowing fingerprinting algorithm — natural language word-token adaptation.

Rebuilt from blingenf/copydetect (MIT License) and the MOSS algorithm
(Schleimer, Wilkerson, Aiken 2003). Adapted for natural language prose:
replaces source-code AST / Pygments lexing with normalized word tokens
(5-grams, window size 4) while preserving character start/end offsets
for exact UI side-by-side highlighting.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

WORD_RE = re.compile(r"\b[A-Za-z0-9А-Яа-яЁё'_-]+\b")


@dataclass
class Token:
    raw: str
    norm: str
    start: int
    end: int


@dataclass
class KGram:
    hash_val: int
    start_char: int
    end_char: int
    token_idx: int


@dataclass
class Fingerprint:
    hash_val: int
    start_char: int
    end_char: int
    token_idx: int


@dataclass
class ExactMatchSpan:
    doc_a_start: int
    doc_a_end: int
    doc_b_start: int
    doc_b_end: int
    text_a: str
    text_b: str


def tokenize_words(text: str) -> list[Token]:
    """Tokenize text into natural language word tokens with character offsets."""
    tokens: list[Token] = []
    for match in WORD_RE.finditer(text):
        raw = match.group()
        norm = raw.lower()
        tokens.append(Token(raw=raw, norm=norm, start=match.start(), end=match.end()))
    return tokens


def hash_kgram(tokens: list[Token]) -> int:
    """Compute robust 64-bit integer hash of normalized word k-gram."""
    norm_seq = " ".join(t.norm for t in tokens)
    digest = hashlib.md5(norm_seq.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def extract_kgrams(tokens: list[Token], k: int = 5) -> list[KGram]:
    """Extract rolling k-grams of word tokens."""
    if len(tokens) < k:
        return []
    kgrams: list[KGram] = []
    for i in range(len(tokens) - k + 1):
        span = tokens[i : i + k]
        h = hash_kgram(span)
        kgrams.append(
            KGram(
                hash_val=h,
                start_char=span[0].start,
                end_char=span[-1].end,
                token_idx=i,
            )
        )
    return kgrams


def winnow_kgrams(kgrams: list[KGram], window_size: int = 4) -> list[Fingerprint]:
    """Apply winnowing algorithm to select minimum hash per sliding window.

    Ties are broken to the right to minimize duplicate selections across
    monotonically shifting windows.
    """
    if not kgrams:
        return []
    if len(kgrams) <= window_size:
        # Window covers all kgrams: select global minimum
        min_kg = min(kgrams, key=lambda kg: kg.hash_val)
        return [
            Fingerprint(
                hash_val=min_kg.hash_val,
                start_char=min_kg.start_char,
                end_char=min_kg.end_char,
                token_idx=min_kg.token_idx,
            )
        ]

    fingerprints: list[Fingerprint] = []
    min_idx = -1
    for i in range(len(kgrams) - window_size + 1):
        window = kgrams[i : i + window_size]
        # Rightmost minimum in window
        window_min = min(window, key=lambda kg: kg.hash_val)
        rightmost_min = [kg for kg in window if kg.hash_val == window_min.hash_val][-1]

        if rightmost_min.token_idx != min_idx:
            min_idx = rightmost_min.token_idx
            fingerprints.append(
                Fingerprint(
                    hash_val=rightmost_min.hash_val,
                    start_char=rightmost_min.start_char,
                    end_char=rightmost_min.end_char,
                    token_idx=rightmost_min.token_idx,
                )
            )
    return fingerprints


def get_fingerprints(text: str, k: int = 5, window_size: int = 4) -> list[Fingerprint]:
    """Extract winnowed fingerprints for a given text."""
    tokens = tokenize_words(text)
    kgrams = extract_kgrams(tokens, k=k)
    return winnow_kgrams(kgrams, window_size=window_size)


def find_exact_matches(
    text_a: str,
    text_b: str,
    k: int = 5,
    window_size: int = 4,
) -> list[ExactMatchSpan]:
    """Find contiguous exact copy spans between Document A and Document B.

    Matches k-grams, tracks character coordinates, and merges overlapping or
    directly adjacent matches into unified highlighting spans.
    """
    tokens_a = tokenize_words(text_a)
    tokens_b = tokenize_words(text_b)
    kgrams_a = extract_kgrams(tokens_a, k=k)
    kgrams_b = extract_kgrams(tokens_b, k=k)

    if not kgrams_a or not kgrams_b:
        return []

    # Map hash -> list of kgram indices in B
    b_map: dict[int, list[int]] = {}
    for idx_b, kg_b in enumerate(kgrams_b):
        b_map.setdefault(kg_b.hash_val, []).append(idx_b)

    # Match raw pairs: (idx_a, idx_b)
    pairs: list[tuple[int, int]] = []
    for idx_a, kg_a in enumerate(kgrams_a):
        if kg_a.hash_val in b_map:
            for idx_b in b_map[kg_a.hash_val]:
                pairs.append((idx_a, idx_b))

    if not pairs:
        return []

    # Sort pairs by (idx_a, idx_b)
    pairs.sort()

    # Form contiguous matching runs
    runs: list[list[tuple[int, int]]] = []
    current_run = [pairs[0]]
    for next_p in pairs[1:]:
        prev_p = current_run[-1]
        # Check if directly sequential
        if next_p[0] == prev_p[0] + 1 and next_p[1] == prev_p[1] + 1:
            current_run.append(next_p)
        elif next_p[0] > prev_p[0]:
            runs.append(current_run)
            current_run = [next_p]
    if current_run:
        runs.append(current_run)

    # Convert runs into ExactMatchSpan
    spans: list[ExactMatchSpan] = []
    for run in runs:
        first_a, first_b = run[0]
        last_a, last_b = run[-1]

        start_a = kgrams_a[first_a].start_char
        end_a = kgrams_a[last_a].end_char
        start_b = kgrams_b[first_b].start_char
        end_b = kgrams_b[last_b].end_char

        spans.append(
            ExactMatchSpan(
                doc_a_start=start_a,
                doc_a_end=end_a,
                doc_b_start=start_b,
                doc_b_end=end_b,
                text_a=text_a[start_a:end_a],
                text_b=text_b[start_b:end_b],
            )
        )

    # Merge overlapping spans in Doc A
    if not spans:
        return []

    spans.sort(key=lambda s: s.doc_a_start)
    merged: list[ExactMatchSpan] = [spans[0]]
    for s in spans[1:]:
        last = merged[-1]
        if s.doc_a_start <= last.doc_a_end:
            # Overlapping or contiguous in Doc A
            new_end_a = max(last.doc_a_end, s.doc_a_end)
            new_end_b = max(last.doc_b_end, s.doc_b_end)
            merged[-1] = ExactMatchSpan(
                doc_a_start=last.doc_a_start,
                doc_a_end=new_end_a,
                doc_b_start=last.doc_b_start,
                doc_b_end=new_end_b,
                text_a=text_a[last.doc_a_start:new_end_a],
                text_b=text_b[last.doc_b_start:new_end_b],
            )
        else:
            merged.append(s)

    return merged
