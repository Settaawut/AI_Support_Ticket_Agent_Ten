"""Tiny dependency-free BM25 index with an English + Thai tokenizer.

Thai is written without spaces, so Thai runs are split into overlapping character
bigrams. Crude, but it needs no dictionary and works well enough for short FAQ text.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[a-z0-9]+|[\u0e00-\u0e7f]+")
_THAI_RE = re.compile(r"[\u0e00-\u0e7f]")
_STOPWORD_TEXT = (
    "a an and are as at be but by can do does for from has have how i if in is it its my "
    "no not of on or so that the their there this to was we what when where which with you "
    "your"
)
_STOPWORDS = frozenset(_STOPWORD_TEXT.split())


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for chunk in _TOKEN_RE.findall(text.lower()):
        if _THAI_RE.match(chunk):
            tokens.extend(chunk[i : i + 2] for i in range(max(len(chunk) - 1, 1)))
        elif chunk not in _STOPWORDS:
            tokens.append(chunk)
    return tokens


@dataclass(frozen=True)
class ScoredDoc:
    index: int
    score: float


class BM25Index:
    def __init__(self, documents: Sequence[str], k1: float = 1.5, b: float = 0.75) -> None:
        self._k1, self._b = k1, b
        self._docs = [Counter(tokenize(doc)) for doc in documents]
        self._lengths = [sum(doc.values()) for doc in self._docs]
        self._avg_len = (sum(self._lengths) / len(self._lengths)) if self._docs else 0.0
        doc_freq = Counter(term for doc in self._docs for term in doc)
        n = len(self._docs)
        self._idf = {t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in doc_freq.items()}

    def search(self, query: str, top_k: int, min_score: float = 0.0) -> list[ScoredDoc]:
        terms = set(tokenize(query))
        scored = [ScoredDoc(i, self._score(i, terms)) for i in range(len(self._docs))]
        hits = [s for s in scored if s.score > min_score]
        return sorted(hits, key=lambda s: s.score, reverse=True)[:top_k]

    def _score(self, i: int, terms: set[str]) -> float:
        doc, length = self._docs[i], self._lengths[i]
        score = 0.0
        for term in terms & doc.keys():
            tf = doc[term]
            norm = tf + self._k1 * (1 - self._b + self._b * length / self._avg_len)
            score += self._idf[term] * tf * (self._k1 + 1) / norm
        return score
