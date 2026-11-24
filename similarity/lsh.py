"""MinHash LSH candidate filtering (Step 6).

Wraps datasketch.MinHash and datasketch.MinHashLSH (MIT License) to index
archived submissions and quickly filter candidate documents before running
fine-grained Winnowing or semantic vector comparisons.
"""

from __future__ import annotations

import re
from typing import Any

from datasketch import MinHash, MinHashLSH

WORD_RE = re.compile(r"\b[A-Za-z0-9А-Яа-яЁё'_-]+\b")


def get_shingles(text: str, shingle_size: int = 3) -> list[str]:
    """Extract normalized word n-gram shingles from text."""
    words = [m.group().lower() for m in WORD_RE.finditer(text)]
    if len(words) < shingle_size:
        return [" ".join(words)] if words else []
    return [" ".join(words[i : i + shingle_size]) for i in range(len(words) - shingle_size + 1)]


def compute_minhash(text: str, num_perm: int = 128, shingle_size: int = 3) -> MinHash:
    """Compute MinHash object for a given text."""
    m = MinHash(num_perm=num_perm)
    shingles = get_shingles(text, shingle_size=shingle_size)
    for s in shingles:
        m.update(s.encode("utf-8"))
    return m


class MinHashIndex:
    """In-memory MinHash LSH index for candidate document filtering."""

    def __init__(
        self,
        threshold: float = 0.2,
        num_perm: int = 128,
        shingle_size: int = 3,
    ) -> None:
        self.threshold = threshold
        self.num_perm = num_perm
        self.shingle_size = shingle_size
        self.lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
        self.minhashes: dict[str, MinHash] = {}

    def index_document(self, doc_id: str, text: str) -> None:
        """Insert or replace a document in the LSH index."""
        if doc_id in self.minhashes:
            self.remove_document(doc_id)
        m = compute_minhash(text, num_perm=self.num_perm, shingle_size=self.shingle_size)
        self.minhashes[doc_id] = m
        self.lsh.insert(doc_id, m)

    def query_candidates(self, text: str) -> list[str]:
        """Query the LSH index for candidate documents with Jaccard similarity >= threshold."""
        m = compute_minhash(text, num_perm=self.num_perm, shingle_size=self.shingle_size)
        candidates = self.lsh.query(m)
        return list(candidates)

    def estimate_jaccard(self, text_a: str, text_b: str) -> float:
        """Estimate the Jaccard similarity between two texts using MinHash."""
        ma = compute_minhash(text_a, num_perm=self.num_perm, shingle_size=self.shingle_size)
        mb = compute_minhash(text_b, num_perm=self.num_perm, shingle_size=self.shingle_size)
        return float(ma.jaccard(mb))

    def remove_document(self, doc_id: str) -> None:
        """Remove a document from the LSH index."""
        if doc_id in self.minhashes:
            self.lsh.remove(doc_id)
            del self.minhashes[doc_id]

    def has_document(self, doc_id: str) -> bool:
        """Check if a document is present in the index."""
        return doc_id in self.minhashes

    def __len__(self) -> int:
        return len(self.minhashes)
