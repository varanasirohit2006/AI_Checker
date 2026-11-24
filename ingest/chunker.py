"""Sentence splitting + sliding-window chunking (AGENTS.md §6B layout).

Windows of ~250 words with 50% overlap (step ~125 words), aligned to sentence
boundaries, with exact character offsets into the input text for UI highlighting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-ZА-ЯЁ0-9])")
WORD_RE = re.compile(r"\S+")


@dataclass
class Sentence:
    text: str
    start: int
    end: int
    n_words: int


@dataclass
class Window:
    text: str
    start_char: int
    end_char: int
    n_words: int
    first_sentence: int
    last_sentence: int


def split_sentences(text: str) -> list[Sentence]:
    sentences = []
    start = 0
    for m in SENTENCE_BOUNDARY.finditer(text):
        chunk = text[start:m.start()]
        if chunk.strip():
            sentences.append(Sentence(chunk, start, m.start(),
                                      len(WORD_RE.findall(chunk))))
        start = m.end()
    tail = text[start:]
    if tail.strip():
        sentences.append(Sentence(tail, start, len(text),
                                  len(WORD_RE.findall(tail))))
    return sentences


def chunk(text: str, window_words: int = 250, overlap: float = 0.5) -> list[Window]:
    sentences = split_sentences(text)
    if not sentences:
        return []
    step_words = max(1, int(window_words * (1 - overlap)))

    windows = []
    i = 0
    n = len(sentences)
    while i < n:
        j = i
        words = 0
        while j < n and words < window_words:
            words += sentences[j].n_words
            j += 1
        start_char = sentences[i].start
        end_char = sentences[j - 1].end
        windows.append(Window(
            text=text[start_char:end_char],
            start_char=start_char,
            end_char=end_char,
            n_words=words,
            first_sentence=i,
            last_sentence=j - 1,
        ))
        if j >= n:
            break
        # advance the start by ~step_words words, staying on sentence boundaries
        acc = 0
        k = i
        while k < j - 1 and acc + sentences[k].n_words <= step_words:
            acc += sentences[k].n_words
            k += 1
        i = k if k > i else i + 1
    return windows