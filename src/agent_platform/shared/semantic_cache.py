"""L3 语义缓存(GPTCache 式,审计 R4/P1 缺口落地)。

- 精确层:归一化键(小写/压缩空白/去标点)→ sha256
- 语义层:字符 3-gram 余弦 ≥ τ(默认 0.92,业界推荐 0.92~0.95)
- 防护:短查询(<8 字符)强制 miss(短/歧义查询误答风险高,业界共识);
        线性扫描 O(n) 教学可接受,生产换向量索引(接口不变)
- 与 InjectionGuard 协同:注入文本先被风控拦截,不进缓存
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass, field

from agent_platform.shared.cache import TwoLevelCache

_SIMILARITY_THRESHOLD = 0.92
_MIN_QUERY_CHARS = 8
_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[,.;:!?、。,;:!?()()\"']")


def normalize(text: str) -> str:
    return _PUNCT.sub("", _WS.sub(" ", text.strip().lower()))


def trigram_vec(text: str) -> Counter[str]:
    t = normalize(text)
    return Counter(t[i : i + 3] for i in range(max(0, len(t) - 2)))


def cosine(a: Counter[str], b: Counter[str]) -> float:
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


@dataclass
class SemanticStats:
    exact_hits: int = 0
    semantic_hits: int = 0
    misses: int = 0
    bypass: int = 0

    def snapshot(self) -> dict[str, float | int]:
        lookups = self.exact_hits + self.semantic_hits + self.misses + self.bypass
        return {
            "lookups": lookups,
            "exact_hits": self.exact_hits,
            "semantic_hits": self.semantic_hits,
            "misses": self.misses,
            "bypass": self.bypass,
            "hit_rate": round((self.exact_hits + self.semantic_hits) / lookups, 4)
            if lookups
            else 0.0,
        }


@dataclass
class SemanticCache:
    """两段式查找:精确 → 语义;阈值 τ 可调,短查询绕过。"""

    threshold: float = _SIMILARITY_THRESHOLD
    exact: TwoLevelCache = field(default_factory=lambda: TwoLevelCache(l1_size=512))
    stats: SemanticStats = field(default_factory=SemanticStats)
    _vectors: list[tuple[Counter, str]] = field(default_factory=list)

    def _key(self, prompt: str) -> str:
        return "llm:" + hashlib.sha256(normalize(prompt).encode()).hexdigest()

    def lookup(self, prompt: str) -> tuple[bool, object | None, str]:
        """返回 (hit, value, via) via ∈ exact/semantic/miss/bypass。"""
        if len(normalize(prompt)) < _MIN_QUERY_CHARS:
            self.stats.bypass += 1
            return False, None, "bypass"
        key = self._key(prompt)
        value = self.exact.get(key)
        if value is not None:
            self.stats.exact_hits += 1
            return True, value, "exact"
        qv = trigram_vec(prompt)
        for cv, cached_key in self._vectors:
            if cosine(qv, cv) >= self.threshold:
                value = self.exact.get(cached_key)
                if value is not None:
                    self.stats.semantic_hits += 1
                    return True, value, "semantic"
        self.stats.misses += 1
        return False, None, "miss"

    def store(self, prompt: str, value: object) -> None:
        key = self._key(prompt)
        self.exact.set(key, value)
        self._vectors.append((trigram_vec(prompt), key))

    def invalidate_all(self) -> None:
        self._vectors.clear()
        self.exact = TwoLevelCache(l1_size=512)
