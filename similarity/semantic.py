"""Semantic paraphrase detection using Sentence-Transformers and FAISS (Step 6).

Embeds sanitized 20–200 word chunks using MiniLM sentence transformers,
indexes normalized vector representations in FAISS (IndexFlatIP), and classifies
matches into severity bands:
  * >= 0.59: low flag
  * >= 0.75: medium paraphrase match
  * >= 0.90: high similarity match

Direct wrapper around sentence-transformers (Apache-2.0) and faiss-cpu (MIT).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

WORD_RE = re.compile(r"\b\S+\b")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ0-9])")

SEVERITY_LOW = 0.59
SEVERITY_MEDIUM = 0.75
SEVERITY_HIGH = 0.90

DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"


@dataclass
class SemanticChunk:
    doc_id: str
    chunk_idx: int
    text: str
    start_char: int
    end_char: int
    n_words: int


@dataclass
class SemanticMatch:
    query_start_char: int
    query_end_char: int
    query_text: str
    matched_doc_id: str
    matched_start_char: int
    matched_end_char: int
    matched_text: str
    similarity: float
    severity: str  # "high" | "medium" | "low"


def split_sentences_with_offsets(text: str) -> list[tuple[str, int, int]]:
    """Split text into sentences preserving start and end character offsets."""
    sentences = []
    start = 0
    for m in SENTENCE_SPLIT_RE.finditer(text):
        chunk_text = text[start:m.start()].strip()
        if chunk_text:
            sentences.append((text[start:m.start()], start, m.start()))
        start = m.end()
    tail = text[start:].strip()
    if tail:
        sentences.append((text[start:], start, len(text)))
    return sentences


def create_semantic_chunks(
    text: str,
    doc_id: str = "query",
    target_words: int = 60,
    min_words: int = 20,
    max_words: int = 200,
) -> list[SemanticChunk]:
    """Segment text into 20–200 word chunks aligned with sentence boundaries."""
    sentences = split_sentences_with_offsets(text)
    if not sentences:
        total_w = len(WORD_RE.findall(text))
        if total_w > 0:
            return [
                SemanticChunk(
                    doc_id=doc_id,
                    chunk_idx=0,
                    text=text,
                    start_char=0,
                    end_char=len(text),
                    n_words=total_w,
                )
            ]
        return []

    chunks: list[SemanticChunk] = []
    current_sentences: list[tuple[str, int, int]] = []
    current_word_count = 0

    for sent_text, s_start, s_end in sentences:
        w_count = len(WORD_RE.findall(sent_text))
        if current_word_count + w_count > max_words and current_sentences:
            # Emit current chunk
            c_text = text[current_sentences[0][1] : current_sentences[-1][2]]
            chunks.append(
                SemanticChunk(
                    doc_id=doc_id,
                    chunk_idx=len(chunks),
                    text=c_text,
                    start_char=current_sentences[0][1],
                    end_char=current_sentences[-1][2],
                    n_words=current_word_count,
                )
            )
            current_sentences = [(sent_text, s_start, s_end)]
            current_word_count = w_count
        else:
            current_sentences.append((sent_text, s_start, s_end))
            current_word_count += w_count
            if current_word_count >= target_words:
                c_text = text[current_sentences[0][1] : current_sentences[-1][2]]
                chunks.append(
                    SemanticChunk(
                        doc_id=doc_id,
                        chunk_idx=len(chunks),
                        text=c_text,
                        start_char=current_sentences[0][1],
                        end_char=current_sentences[-1][2],
                        n_words=current_word_count,
                    )
                )
                current_sentences = []
                current_word_count = 0

    if current_sentences:
        # Check if tail chunk should merge or stand alone
        if current_word_count < min_words and chunks:
            # Extend last chunk
            last = chunks[-1]
            c_text = text[last.start_char : current_sentences[-1][2]]
            chunks[-1] = SemanticChunk(
                doc_id=doc_id,
                chunk_idx=last.chunk_idx,
                text=c_text,
                start_char=last.start_char,
                end_char=current_sentences[-1][2],
                n_words=last.n_words + current_word_count,
            )
        else:
            c_text = text[current_sentences[0][1] : current_sentences[-1][2]]
            chunks.append(
                SemanticChunk(
                    doc_id=doc_id,
                    chunk_idx=len(chunks),
                    text=c_text,
                    start_char=current_sentences[0][1],
                    end_char=current_sentences[-1][2],
                    n_words=current_word_count,
                )
            )

    return chunks


def classify_severity(similarity: float) -> str:
    """Classify cosine similarity into severity tier."""
    if similarity >= SEVERITY_HIGH:
        return "high"
    if similarity >= SEVERITY_MEDIUM:
        return "medium"
    if similarity >= SEVERITY_LOW:
        return "low"
    return "none"


class SemanticIndex:
    """FAISS-based dense semantic chunk index for paraphrase retrieval."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        device: str = "cpu",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.model = SentenceTransformer(model_name, device=device)
        if hasattr(self.model, "get_embedding_dimension"):
            self.embedding_dim = self.model.get_embedding_dimension()
        else:
            self.embedding_dim = self.model.get_sentence_embedding_dimension()

        # Inner-product index on L2-normalized embeddings == Cosine Similarity
        self.index = faiss.IndexFlatIP(self.embedding_dim)
        self.chunks: list[SemanticChunk] = []
        self.doc_chunk_map: dict[str, list[int]] = {}

    def index_document(self, doc_id: str, text: str) -> list[SemanticChunk]:
        """Chunk, embed, and index a document in FAISS."""
        chunks = create_semantic_chunks(text, doc_id=doc_id)
        if not chunks:
            return []

        texts = [c.text for c in chunks]
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype("float32")

        start_id = len(self.chunks)
        self.index.add(embeddings)
        self.chunks.extend(chunks)

        chunk_ids = list(range(start_id, start_id + len(chunks)))
        self.doc_chunk_map[doc_id] = chunk_ids
        return chunks

    def search_text(
        self,
        query_text: str,
        min_similarity: float = SEVERITY_LOW,
        top_k: int = 5,
        exclude_doc_id: str | None = None,
    ) -> list[SemanticMatch]:
        """Find semantic paraphrase matches for query text against the index."""
        if self.index.ntotal == 0:
            return []

        query_chunks = create_semantic_chunks(query_text, doc_id="query")
        if not query_chunks:
            return []

        query_texts = [c.text for c in query_chunks]
        query_embeddings = self.model.encode(
            query_texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype("float32")

        distances, indices = self.index.search(query_embeddings, min(top_k, self.index.ntotal))

        matches: list[SemanticMatch] = []
        for q_idx, q_chunk in enumerate(query_chunks):
            for rank in range(distances.shape[1]):
                sim = float(distances[q_idx, rank])
                matched_idx = int(indices[q_idx, rank])
                if matched_idx < 0 or matched_idx >= len(self.chunks):
                    continue
                if sim < min_similarity:
                    continue

                target_chunk = self.chunks[matched_idx]
                if exclude_doc_id and target_chunk.doc_id == exclude_doc_id:
                    continue

                severity = classify_severity(sim)
                matches.append(
                    SemanticMatch(
                        query_start_char=q_chunk.start_char,
                        query_end_char=q_chunk.end_char,
                        query_text=q_chunk.text,
                        matched_doc_id=target_chunk.doc_id,
                        matched_start_char=target_chunk.start_char,
                        matched_end_char=target_chunk.end_char,
                        matched_text=target_chunk.text,
                        similarity=sim,
                        severity=severity,
                    )
                )

        return matches
