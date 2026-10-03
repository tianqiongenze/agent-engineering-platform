"""多级缓存(L1 进程内 LRU + L2 外部 KV):命中率全程可观测。

审计报告 R4 缺口落地:此前"缓存"只存在于设计文档;本模块让
命中率/层级命中分布成为可实测、可上报的一等指标。
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Protocol


class KVStore(Protocol):
    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, ttl_s: float | None = None) -> None: ...


class InMemoryKV:
    """L2 的教学实现(生产换 Redis,接口不变);带 TTL 惰性过期。"""

    def __init__(self, max_entries: int = 10_000) -> None:
        self._data: dict[str, tuple[Any, float | None]] = {}
        self._max = max_entries

    def get(self, key: str) -> Any | None:
        item = self._data.get(key)
        if item is None:
            return None
        value, expires = item
        if expires is not None and expires < time.monotonic():
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl_s: float | None = None) -> None:
        if len(self._data) >= self._max and key not in self._data:
            self._data.pop(next(iter(self._data)))  # 简易 FIFO 淘汰
        expires = time.monotonic() + ttl_s if ttl_s else None
        self._data[key] = (value, expires)


@dataclass
class CacheStats:
    l1_hits: int = 0
    l2_hits: int = 0
    misses: int = 0

    @property
    def lookups(self) -> int:
        return self.l1_hits + self.l2_hits + self.misses

    @property
    def hit_rate(self) -> float:
        return (self.l1_hits + self.l2_hits) / self.lookups if self.lookups else 0.0

    def snapshot(self) -> dict[str, float | int]:
        return {
            "lookups": self.lookups,
            "l1_hits": self.l1_hits,
            "l2_hits": self.l2_hits,
            "misses": self.misses,
            "hit_rate": round(self.hit_rate, 4),
        }


class TwoLevelCache:
    """L1 LRU(纳秒级)→ L2 外部 KV(跨进程)→ 回源。

    命中层级统计让"缓存还有没有提升空间"变成可回答的问题:
    L1 命中率低 → 调大容量;L2 命中低 → 检查 TTL/键设计。
    """

    def __init__(
        self, l1_size: int = 256, l2: KVStore | None = None, default_ttl_s: float | None = None
    ) -> None:
        self._l1: OrderedDict[str, Any] = OrderedDict()
        self._l1_size = l1_size
        self._l2 = l2 or InMemoryKV()
        self.default_ttl = default_ttl_s
        self.stats = CacheStats()
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key in self._l1:
                self._l1.move_to_end(key)
                self.stats.l1_hits += 1
                return self._l1[key]
        value = self._l2.get(key)
        if value is not None:
            with self._lock:
                self.stats.l2_hits += 1
                self._l1[key] = value
                self._l1.move_to_end(key)
                if len(self._l1) > self._l1_size:
                    self._l1.popitem(last=False)
            return value
        with self._lock:
            self.stats.misses += 1
        return None

    def set(self, key: str, value: Any, ttl_s: float | None = None) -> None:
        with self._lock:
            self._l1[key] = value
            self._l1.move_to_end(key)
            if len(self._l1) > self._l1_size:
                self._l1.popitem(last=False)
        self._l2.set(key, value, ttl_s if ttl_s is not None else self.default_ttl)

    def get_or_load(self, key: str, loader: Any, ttl_s: float | None = None) -> Any:
        """旁路缓存:miss 时回源并回填。"""
        value = self.get(key)
        if value is not None:
            return value
        value = loader()
        self.set(key, value, ttl_s)
        return value

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._l1.pop(key, None)
        if hasattr(self._l2, "_data"):
            self._l2._data.pop(key, None)  # type: ignore[attr-defined]  # 教学实现直清
