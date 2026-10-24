"""风控层(防重/防刷/防注入)—— 审计报告 R1~R3 缺口的落地。

- TokenBucketRateLimiter:接口级防刷(令牌桶,per-key)
- ReplayGuard:幂等键/nonce 去重,防重放
- InjectionGuard:Prompt 注入模式拦截
全部纯内存实现零依赖;Redis 化为适配点(接口不变)。
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field


class RateLimitExceeded(RuntimeError):
    pass


class ReplayDetected(RuntimeError):
    pass


class InjectionDetected(RuntimeError):
    pass


class TokenBucketRateLimiter:
    """令牌桶:每 key 独立桶;capacity 桶深,refill_per_s 回填速率。"""

    def __init__(self, capacity: int = 10, refill_per_s: float = 2.0) -> None:
        if capacity <= 0 or refill_per_s <= 0:
            raise ValueError("capacity/refill must be positive")
        self.capacity = capacity
        self.refill_per_s = refill_per_s
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, ts)
        self._lock = threading.Lock()
        self.rejected = 0
        self._last_sweep = 0.0
        self._MAX_BUCKETS = 100_000  # P1:按 key 洪泛设上界

    def acquire(self, key: str, cost: float = 1.0) -> None:
        with self._lock:
            now = time.monotonic()
            # P1 修复:周期性惰性清扫过期桶(空桶 10 分钟未用即回收)
            if now - self._last_sweep > 60 and len(self._buckets) > self._MAX_BUCKETS:
                cutoff = now - 600
                self._buckets = {
                    k: v for k, v in self._buckets.items() if v[1] > cutoff
                }
                self._last_sweep = now
            tokens, ts = self._buckets.get(key, (float(self.capacity), now))
            tokens = min(self.capacity, tokens + (now - ts) * self.refill_per_s)
            if tokens < cost:
                self._buckets[key] = (tokens, now)
                self.rejected += 1
                raise RateLimitExceeded(f"rate limited for {key}")
            self._buckets[key] = (tokens - cost, now)


class ReplayGuard:
    """幂等键去重:TTL 窗口内相同 key 视为重放。"""

    def __init__(self, ttl_s: float = 300.0, max_entries: int = 100_000) -> None:
        self.ttl = ttl_s
        self.max_entries = max_entries
        self._seen: dict[str, float] = {}
        self._lock = threading.Lock()
        self.blocked = 0

    def check(self, idempotency_key: str) -> None:
        if not idempotency_key:
            return  # 未携带幂等键不拦截(由上层决定是否强制)
        with self._lock:
            now = time.monotonic()
            if len(self._seen) > self.max_entries:
                cutoff = now - self.ttl
                self._seen = {k: t for k, t in self._seen.items() if t >= cutoff}
            first_seen = self._seen.get(idempotency_key)
            if first_seen is not None and now - first_seen < self.ttl:
                self.blocked += 1
                raise ReplayDetected(f"replay detected: {idempotency_key[:16]}")
            self._seen[idempotency_key] = now
            # P1 修复:清理后仍超限则强制截断(防唯一 key 洪泛)
            if len(self._seen) > self.max_entries:
                cutoff = now - self.ttl
                self._seen = {k: v for k, v in self._seen.items() if v >= cutoff}
                if len(self._seen) > self.max_entries:
                    for k in list(self._seen)[: len(self._seen) - self.max_entries]:
                        del self._seen[k]


_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts)",
        r"disregard\s+(your|all|the)\s+(instructions|rules)",
        r"你(是|现在起变成)(DAN|无限制)",
        r"(system|developer)\s*(prompt|message)\s*[:]",
        r"</?(system|assistant)>",
        r"reveal\s+your\s+(system\s+)?prompt",
    )
]


class InjectionGuard:
    """Prompt 注入模式拦截(黑名单起步;生产可升级为分类器)。"""

    def __init__(self, extra_patterns: list[str] | None = None) -> None:
        self.patterns = list(_INJECTION_PATTERNS) + [
            re.compile(p, re.IGNORECASE) for p in (extra_patterns or [])
        ]
        self.blocked = 0

    def check(self, text: str) -> None:
        for pat in self.patterns:
            if pat.search(text):
                self.blocked += 1
                raise InjectionDetected(f"injection pattern matched: {pat.pattern[:40]}")


@dataclass
class SecurityStack:
    @staticmethod
    def limiter_factory(capacity: int, refill_per_s: float) -> TokenBucketRateLimiter:
        return TokenBucketRateLimiter(capacity=capacity, refill_per_s=refill_per_s)

    """API 入口风控组合:顺序 = 注入 → 重放 → 限流。"""

    limiter: TokenBucketRateLimiter = field(default_factory=TokenBucketRateLimiter)
    replay: ReplayGuard = field(default_factory=ReplayGuard)
    injection: InjectionGuard = field(default_factory=InjectionGuard)

    def check_request(self, *, client_key: str, text: str, idempotency_key: str = "") -> None:
        self.injection.check(text)
        self.replay.check(idempotency_key)
        self.limiter.acquire(client_key)
