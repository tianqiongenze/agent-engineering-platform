"""BC4 · Hybrid RAG(阶段四):向量 stub + BM25 简化 + RRF 融合。

教学实现零外部依赖;Milvus 适配器在集成层替换 VectorChannel(接口不变)。
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

_RRF_K = 60


@dataclass
class Chunk:
    id: str
    text: str
    source: str


@dataclass
class ScoredChunk:
    chunk: Chunk
    score: float
    via: str  # bm25 | vector | both


def _tokenize(text: str) -> list[str]:
    return [t for t in text.lower().replace("(", " ").replace(")", " ").split() if t]


class _BM25:
    def __init__(self, corpus: list[Chunk]) -> None:
        self.corpus = corpus
        self.doc_freq: Counter[str] = Counter()
        self.tokens: dict[str, list[str]] = {}
        for c in corpus:
            toks = _tokenize(c.text)
            self.tokens[c.id] = toks
            self.doc_freq.update(set(toks))
        self.avg_len = sum(len(t) for t in self.tokens.values()) / max(1, len(corpus))

    def rank(self, query: str) -> list[tuple[str, float]]:
        q = _tokenize(query)
        scores: list[tuple[str, float]] = []
        n = len(self.corpus)
        for cid, toks in self.tokens.items():
            tf = Counter(toks)
            s = 0.0
            for term in q:
                if term not in tf:
                    continue
                df = self.doc_freq[term]
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                s += (
                    idf
                    * (tf[term] * 2.2)
                    / (tf[term] + 1.2 * (1 - 0.75 + 0.75 * len(toks) / self.avg_len))
                )
            if s > 0:
                scores.append((cid, s))
        return sorted(scores, key=lambda x: -x[1])


class _NgramVector:
    """字符 3-gram 余弦:教学用语义通道替身(生产换 Embedding+Milvus)。"""

    @staticmethod
    def _vec(text: str) -> Counter[str]:
        t = text.lower()
        return Counter(t[i : i + 3] for i in range(max(0, len(t) - 2)))

    def rank(self, corpus: list[Chunk], query: str) -> list[tuple[str, float]]:
        qv = self._vec(query)
        out: list[tuple[str, float]] = []
        for c in corpus:
            cv = self._vec(c.text)
            dot = sum(min(qv[g], cv[g]) for g in qv if g in cv)
            norm = math.sqrt(sum(v * v for v in qv.values())) * math.sqrt(
                sum(v * v for v in cv.values())
            )
            if dot > 0 and norm > 0:
                out.append((c.id, dot / norm))
        return sorted(out, key=lambda x: -x[1])


class HybridRetriever:
    def __init__(self, corpus: list[Chunk]) -> None:
        self.corpus = corpus
        self.bm25 = _BM25(corpus)
        self.vector = _NgramVector()
        self._by_id = {c.id: c for c in corpus}

    def search(self, query: str, k: int = 4) -> list[ScoredChunk]:
        kw = self.bm25.rank(query)
        vec = self.vector.rank(self.corpus, query)
        rrf: dict[str, float] = {}
        via: dict[str, set[str]] = {}
        for rank, (cid, _score) in enumerate(kw):
            rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)
            via.setdefault(cid, set()).add("bm25")
        for rank, (cid, _score) in enumerate(vec):
            rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)
            via.setdefault(cid, set()).add("vector")
        fused = sorted(rrf.items(), key=lambda x: -x[1])[:k]
        return [
            ScoredChunk(
                chunk=self._by_id[cid], score=score, via="+".join(sorted(via.get(cid, set())))
            )
            for cid, score in fused
        ]
